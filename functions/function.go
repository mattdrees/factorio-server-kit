package cleanup

import (
	"github.com/GoogleCloudPlatform/functions-framework-go/functions"
)

// init registers the cleanup functions as 2nd-gen Cloud Function CloudEvent handlers.
// The entry-point names ("Instances", "Disks") match the --entry-point values used by deploy.sh.
func init() {
	functions.CloudEvent("Instances", Instances)
	functions.CloudEvent("Disks", Disks)
}
