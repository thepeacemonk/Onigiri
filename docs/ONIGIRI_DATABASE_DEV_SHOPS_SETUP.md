# Onigiri Database: developer Nooks setup

The add-on now sends the following developer Nooks to the Onigiri Database:

| Restaurant ID | Onigiri name | Rush group | Rush title | Theme |
|---|---|---|---|---|
| `koeni_nook` | Koeni's Maple Mornings | `koeni_maple` | Maple Morning Rush | `#D9822B` |
| `dyzur_sushi` | Dyzur's Nigiri Nook | `dyzur_nigiri` | Nigiri Nook Rush | `#2F8575` |
| `max_udon_recoin` | Max Udon Recoin | `max_udon` | Udon Recoin Rush | `#274A82` |
| `maxims_shop` | Maxim's Golden Fry | `maxim_fry` | Golden Fry Rush | `#D64A2D` |
| `mochi_girl_shop` | MochiGirl's Phở Nook | `mochigirl_pho` | Phở Nook Rush | `#4E8D45` |
| `nitro_nook` | Nitro's Poppy Corners | `nitro_popcorn` | Poppy Corners Rush | `#D65732` |
| `royal_kulfi` | H0tp's kulfi | `royal_kulfi` | H0tp's Kulfi Rush | `#BE3958` |
| `tinamon_nook` | Tinamon's Souvlaki | `tinamon_souvlaki` | Souvlaki Rush | `#2458A6` |

Wizard Shop, Paws & Whiskers, and Dino Shop already had Rush IDs and recipe
pools in the supplied Apps Script. Their missing local images are now connected.

## Update the Apps Script

1. Back up the Google Sheet and the current Apps Script project.
2. Open the spreadsheet, then open **Extensions → Apps Script**.
3. Replace the database web-app source with the updated
   [supplied script](../integrations/apps_script/Onigiri_Database_Apps_Script.gs).
4. Save the project. If Google requests authorization while deploying, approve
   the spreadsheet access used by the existing database script.
5. Use **Deploy → Manage deployments**, edit the existing web-app deployment,
   select a new version, and deploy it. Updating the existing deployment keeps
   the `/exec` URL already embedded in Onigiri.
6. Keep the web app executing as the deploying user. It must allow anonymous
   access because the desktop add-on posts JSON without a Google sign-in
   (`executeAs: USER_DEPLOYING`, `access: ANYONE_ANONYMOUS`).

If a brand-new deployment is created instead, copy its `/exec` URL into both
`RECIPE_RUSH_API_URL` in `gamification/nook_level.py` and `SHOP_API_URL` in
`gamification/nook_web_ui.py`.

## Update and verify the spreadsheet

Do not manually add columns or delete existing recipe rows. The updated script
keeps existing data and performs the following additive migration on the next
Rush request:

- Rebuilds the informational **Rush Groups** sheet from the code, adding the eight
  groups above.
- Appends 30 starter recipes for each new group (240 rows total) to **Recipe
  Rush Recipes** only when that group has no rows yet.
- Adds the eight Nooks to **Recipe Rush Restaurants** when the updated add-on sends
  its catalog. Existing restaurant records and custom recipes are preserved.

To trigger and verify the migration:

1. Restart Anki after installing the changed add-on files.
2. Open Mr. Taiyaki's Store and confirm the **Developers** category contains eight
   Nooks. Wizard Shop, Paws & Whiskers, and Dino Shop should now show artwork.
3. Buy/equip one developer Nook.
4. Open **Settings → Gamification → Nook Level** and choose **Sync Rush Now**.
5. In the spreadsheet, confirm:
   - **Rush Groups** has each of the eight group keys in the table above.
   - **Recipe Rush Recipes** has 30 `Active` rows for each new group.
   - **Recipe Rush Restaurants** contains all eight IDs with type `developer`.
6. Return to Nook Level and confirm the equipped Nook shows its named Rush,
   recipe ingredients, artwork, and matching accent color.

To customize a pool later, edit its rows directly in **Recipe Rush Recipes**.
Use a listed Rush Group key and `Active`/`Inactive` in the Status column; no
redeploy is needed for recipe-row edits.
