//go:build !windows

package studiohost

import (
	"fmt"
	"os"
)

func ReportStartupError(prefix string, err error) {
	fmt.Fprintln(os.Stderr, prefix+":", err)
}
