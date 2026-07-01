//go:build windows

package studiohost

import (
	"fmt"
	"os"
	"syscall"
	"unsafe"
)

func ReportStartupError(prefix string, err error) {
	text := prefix + ".\r\n\r\n" + err.Error() + "\r\n\r\nA private diagnostic log may be available under Local AppData."
	title := "Dash-Go Showcase Studio"
	user32 := syscall.NewLazyDLL("user32.dll")
	proc := user32.NewProc("MessageBoxW")
	_, _, _ = proc.Call(0, uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(text))), uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(title))), 0x00000010)
	if os.Getenv("DASHGO_SHOWCASE_CLI") == "1" {
		fmt.Fprintln(os.Stderr, prefix+":", err)
	}
}
