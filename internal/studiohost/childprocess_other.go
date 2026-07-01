//go:build !windows

package studiohost

import "os/exec"

func prepareStudioChildCommand(cmd *exec.Cmd) {}
