# Dash-Go Showcase Studio

Dash-Go Showcase Studio runs a private, disposable demonstration of the real Dash-Go dashboard. It never modifies a normal Dash-Go installation, calendar, account, browser profile, device setting, or display configuration.

## Start

Open **Dash-Go Showcase Studio**, choose a demo city, and select **Start Tour**. The Tour creates fresh fictional household data and guides you through real Dash-Go views. Closing Studio removes its private workspace and browser profile.

The Tour temporarily previews the Lists dock and a clearly labeled sample weather alert. Both disappear when the Tour ends. The underlying Dash-Go defaults remain unchanged.

## Demo locations

New York, Chicago, Denver, Los Angeles, Anchorage, and Honolulu are available. The selected city shapes synthetic calendar dates, map coordinates, weather-ready settings, event wording, sample alerts, and Studio messages. Location search is available as a preview, but Studio always retains its selected demo city.

## Showcase View

A running Studio session has a small **Showcase View** tab. It can change the private browser’s live CSS viewport without changing Windows or Linux display settings:

- Fit Display
- 1920×1080, 1366×768, 1280×800, and 1024×600 landscape previews
- 1080×1920, 800×1280, 768×1024, and 600×1024 portrait previews
- Clean View for a Studio-chrome-free demonstration

The selected viewport is session-only and resets to Fit Display next launch.

## Studio boundaries

Household apps and cosmetic settings remain interactive inside the disposable session. System actions, real updates, account/sync setup, imports/restores, external notification delivery, PIN changes, and location commits are blocked by the staged Studio runtime.

## Support actions

The CLI companion supports `--action diagnose`, `--action self-test`, `--action clean`, and `--action purge`. These are used by the Builder and are not part of ordinary Studio use.
