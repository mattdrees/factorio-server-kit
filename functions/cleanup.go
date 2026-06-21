// Package cleanup holds funcs which are executed on a regular basis.
package cleanup

const (
	statusTerminated = "TERMINATED"

	fmtLocationsBucket = "%s-storage"
	locationsObject    = "lib/locations.json"
)

// location describes the structure of a JSON file that we use to denote which GCP regions and zones are in use by this
// project.
type location struct {
	Location string   `json:"location"`
	Zones    []string `json:"zones"`
}
