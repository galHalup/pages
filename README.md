# Year Review Generator

A reusable system to generate year-in-review pages for team members and team summaries. Collects data from GitHub, Slack, and Google Calendar (ICS files) to create beautiful timeline infographics.

## Features

- **Multi-source data collection**: GitHub (PRs, reviews, commits), Slack (messages), Google Calendar (events)
- **Automatic project detection**: Groups related activities into projects with timelines
- **Interactive timeline**: Quarterly project breakdowns with clickable modals
- **Team summary page**: Overview of all team members with individual drill-down pages
- **Reusable**: Config-driven, easy to update for next year

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure team members**:
   Edit `config/team_config.json` with your team's information:
   - GitHub usernames
   - Slack emails
   - Calendar file paths
   - Repository list

3. **Add credentials** (already in config, but update if needed):
   - GitHub Personal Access Token (PAT)
   - Slack OAuth Token
   - Calendar folder path

## Usage

1. **Place calendar files** in the configured calendar folder (default: `/Users/galh/Downloads/calanders/`)

2. **Run data collection**:
   ```bash
   python scripts/collect_data.py
   ```

   This will:
   - Collect data from GitHub, Slack, and Calendar
   - Analyze and group projects
   - Generate HTML pages for each team member
   - Generate team summary page

3. **View generated pages**:
   - Team summary: `generated/index.html`
   - Individual pages: `generated/{username}.html`

4. **Deploy to GitHub Pages**:
   ```bash
   git add generated/
   git commit -m "Generate year review pages"
   git push
   ```

   Then enable GitHub Pages in your repository settings to point to the `generated/` directory.

## Configuration

### Team Config (`config/team_config.json`)

```json
{
  "year": 2025,
  "team_name": "Your Team Name",
  "github_pat": "your_github_pat",
  "slack_token": "your_slack_token",
  "calendar_folder": "/path/to/calendars",
  "members": [
    {
      "name": "Member Name",
      "github": "github_username",
      "slack": "email@company.com",
      "calendar_file": "filename.ics",
      "has_calendar": true
    }
  ],
  "repositories": [
    "org/repo1",
    "org/repo2"
  ]
}
```

## Project Detection

Projects are automatically detected from:
- PR titles and descriptions
- Calendar event titles
- Keywords defined in `project_keywords` config

Projects are categorized as:
- Infrastructure
- Feature
- Performance
- Security
- AI
- Cost
- Team

## Data Storage

Collected data is stored in `data/raw/` as JSON files:
- `{username}_data.json` - Raw collected data
- `{username}_projects.json` - Analyzed projects

Data is cached - re-running will use cached data unless files are deleted.

## Customization

### Templates

- `templates/individual_template.html` - Individual team member page
- `templates/team_template.html` - Team summary page

Both use Jinja2 templating. Modify styles and structure as needed.

### Project Keywords

Edit `project_keywords` in config to improve project detection and categorization.

## Troubleshooting

### GitHub API Rate Limits
The script handles rate limiting automatically, but if you hit limits:
- Wait for rate limit reset
- Or reduce the number of repositories being scanned

### Slack API Errors
- Verify Slack token has necessary scopes
- Check that user emails match Slack workspace emails

### Calendar Parsing Issues
- Ensure ICS files are valid
- Check file paths in config
- For zip files, ensure they contain valid ICS files

## Next Year

To generate reviews for a new year:
1. Update `year` in `config/team_config.json`
2. Update team members if needed
3. Place new calendar files
4. Run `python scripts/collect_data.py`

## License

Internal use only.

