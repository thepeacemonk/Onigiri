# Onigiri Communications and Announcements

Onigiri's **Communications** inbox reads published messages from the
**Announcements** tab in the Onigiri Database spreadsheet. The tab is created
with its header row the first time a user syncs Communications.

## Announcements sheet

Use one announcement per row with these columns in row 1:

| Announcement ID | Title | Message | Image URL | Status | Publish At | Expires At |
|---|---|---|---|---|---|---|

- **Announcement ID** can be left blank; Apps Script fills in a stable ID the
  first time it publishes that row.
- **Title** and **Message** are the announcement text. The message is plain
  text; line breaks are preserved.
- **Image URL** is optional. For Google Drive images, upload the image, set its
  sharing access to **Anyone with the link — Viewer**, then paste the share URL.
  The image will be visible to everyone who syncs the inbox. A public direct
  HTTPS image URL also works.
- Set **Status** to `Active` to publish to all Onigiri users of this database;
  set it to `Inactive` to remove it from the next inbox sync.
- **Publish At** and **Expires At** are optional date/time cells. Blank means
  publish immediately or do not expire. Future publish dates and expired
  announcements are hidden.

## Enable it

1. Back up the Google Sheet and Apps Script project.
2. Replace the Apps Script project source with the complete
   `Onigiri_Database_Apps_Script.gs` file and save it.
3. In **Deploy → Manage deployments**, edit the existing web-app deployment,
   select a new version, and deploy. Keep the same deployment and `/exec` URL.
4. Install the updated Onigiri add-on and restart Anki.
5. Open **Onigiri → Gamification → Communications**, then click
   **Sync announcements**. The inbox caches messages and read status locally
   for the current Anki profile. Read status is not sent back to the sheet.

Only active, currently published messages are returned by the database. Sync
again after editing a message or changing its status to refresh users' inboxes.
Once the updated Apps Script is deployed, adding or editing announcement rows
does not require another deployment.
