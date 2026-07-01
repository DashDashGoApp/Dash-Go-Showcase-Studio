package studiohost

import (
	"errors"
	"fmt"
	"syscall"
	"testing"
	"time"
)

func TestRetryWorkspaceRenameRetriesTransientWindowsAccessDenied(t *testing.T) {
	calls := 0
	sleeps := 0
	err := retryWorkspaceRename(
		func(_, _ string) error {
			calls++
			if calls < 3 {
				return syscall.EACCES
			}
			return nil
		},
		func(time.Duration) { sleeps++ },
		true,
		"stage",
		"workspace",
	)
	if err != nil {
		t.Fatalf("retryWorkspaceRename returned error: %v", err)
	}
	if calls != 3 || sleeps != 2 {
		t.Fatalf("calls=%d sleeps=%d, want calls=3 sleeps=2", calls, sleeps)
	}
}

func TestRetryWorkspaceRenameDoesNotRetryOutsideWindows(t *testing.T) {
	calls := 0
	err := retryWorkspaceRename(
		func(_, _ string) error {
			calls++
			return syscall.EACCES
		},
		func(time.Duration) { t.Fatal("sleep should not be called outside Windows") },
		false,
		"stage",
		"workspace",
	)
	if err == nil || calls != 1 {
		t.Fatalf("err=%v calls=%d, want one failed call", err, calls)
	}
	if !errors.Is(err, syscall.EACCES) {
		t.Fatalf("error does not preserve access denied: %v", err)
	}
}

func TestRetryWorkspaceRenameDoesNotRetryNonTransientWindowsFailure(t *testing.T) {
	calls := 0
	err := retryWorkspaceRename(
		func(_, _ string) error {
			calls++
			return fmt.Errorf("rename failed: %w", syscall.ENOENT)
		},
		func(time.Duration) { t.Fatal("sleep should not be called for a non-transient error") },
		true,
		"stage",
		"workspace",
	)
	if err == nil || calls != 1 {
		t.Fatalf("err=%v calls=%d, want one failed call", err, calls)
	}
	if !errors.Is(err, syscall.ENOENT) {
		t.Fatalf("error does not preserve ENOENT: %v", err)
	}
}

func TestWorkspaceRenameBackoffIsBounded(t *testing.T) {
	if got := workspaceRenameBackoff(0); got != workspaceRenameInitialDelay {
		t.Fatalf("first delay=%s, want %s", got, workspaceRenameInitialDelay)
	}
	if got := workspaceRenameBackoff(20); got != workspaceRenameMaximumDelay {
		t.Fatalf("late delay=%s, want %s", got, workspaceRenameMaximumDelay)
	}
}
