//go:build windows

package studiohost

import (
	"os/exec"
	"syscall"
)

const createNoWindow = 0x08000000

func prepareStudioChildCommand(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
}
