package cleanup

import (
	"context"
	"fmt"

	"cloud.google.com/go/compute/metadata"
	"github.com/cloudevents/sdk-go/v2/event"
	"google.golang.org/api/compute/v1"
)

// Instances iterates across all zones listed in gs://<project>-storage/lib/locations.json file deleting all VMs which:
// (1) are named using the same pattern that /scripts/roll-vm.sh uses to create instances.
// (2) have a status of TERMINATED.
//
// It is a 2nd-gen Cloud Function CloudEvent handler; the Pub/Sub message that triggers it carries no payload we use.
func Instances(ctx context.Context, _ event.Event) error {
	projectID, err := metadata.ProjectID()
	if err != nil {
		return fmt.Errorf("error fetching project ID from metadata: %w", err)
	}

	locs, err := locations(ctx, projectID)
	if err != nil {
		return err
	}

	computeService, err := compute.NewService(ctx)
	if err != nil {
		return fmt.Errorf("error creating Compute service: %w", err)
	}

	// We match on the generic "factorio-*" prefix rather than "factorio-<location>-*"
	// scoped to that location's zones. Capacity fallback can create a VM in a
	// different region than its name suggests (e.g. a "factorio-iowa-*" VM landing
	// in a us-west2 zone), so coupling the name filter to the zone's location would
	// let those cross-region fallback VMs slip through cleanup forever. Zones are
	// disjoint across locations, so every zone is still visited exactly once.
	for _, loc := range locs {
		for _, zone := range loc.Zones {
			listCall := computeService.Instances.List(projectID, zone)
			listCall = listCall.Filter("name:factorio-*")

			list, err := listCall.Do()
			if err != nil {
				return fmt.Errorf("error listing instances in zone %s: %w", zone, err)
			}

			for _, inst := range list.Items {
				if inst.Status == statusTerminated {
					deleteCall := computeService.Instances.Delete(projectID, zone, inst.Name)

					if _, err := deleteCall.Do(); err != nil {
						return fmt.Errorf("error executing delete operation for instance %s in zone %s: %w",
							inst.Name, zone, err)
					}
				}
			}
		}
	}

	return nil
}
