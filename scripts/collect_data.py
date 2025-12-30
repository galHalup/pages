#!/usr/bin/env python3
"""
Main data collection script for year review.
Orchestrates all collectors and generators.
"""

import json
import sys
from pathlib import Path
from typing import Dict

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from github_collector import GitHubCollector
from slack_collector import SlackCollector
from calendar_parser import CalendarParser
from project_analyzer import ProjectAnalyzer
from generate_pages import PageGenerator


def collect_member_data(member: Dict, config: Dict) -> Dict:
    """Collect all data for a team member."""
    print(f"\n{'='*60}")
    print(f"Collecting data for: {member['name']}")
    print(f"{'='*60}\n")
    
    data = {
        'github': {},
        'slack': {},
        'calendar': {}
    }
    
    # Collect GitHub data
    if member.get('github'):
        try:
            github_collector = GitHubCollector(config['github_pat'], config['year'])
            github_data = github_collector.collect_user_data(
                member['github'],
                config['repositories']
            )
            data['github'] = github_data
            print(f"✓ Collected {len(github_data.get('prs_authored', []))} PRs, "
                  f"{len(github_data.get('prs_reviewed', []))} reviews")
        except Exception as e:
            print(f"✗ Error collecting GitHub data: {e}")
    else:
        print("⊘ Skipping GitHub (no username)")
    
    # Collect Slack data
    if member.get('slack'):
        try:
            slack_collector = SlackCollector(config['slack_token'], config['year'])
            slack_data = slack_collector.get_user_messages(member['slack'])
            data['slack'] = slack_data
            print(f"✓ Collected {slack_data.get('total_messages', 0)} Slack messages")
        except Exception as e:
            print(f"✗ Error collecting Slack data: {e}")
    else:
        print("⊘ Skipping Slack (no email)")
    
    # Collect Calendar data
    if member.get('has_calendar') and member.get('calendar_file'):
        try:
            calendar_parser = CalendarParser(config['calendar_folder'], config['year'])
            calendar_data = calendar_parser.parse_user_calendar(member['calendar_file'])
            data['calendar'] = calendar_data
            print(f"✓ Collected {calendar_data.get('total_events', 0)} calendar events")
        except Exception as e:
            print(f"✗ Error collecting Calendar data: {e}")
    else:
        print("⊘ Skipping Calendar (no file or not shared)")
    
    return data


def analyze_projects(member: Dict, data: Dict, config: Dict) -> Dict:
    """Analyze and group projects for a team member."""
    print(f"\nAnalyzing projects for {member['name']}...")
    
    analyzer = ProjectAnalyzer(config.get('project_keywords', {}))
    
    # Analyze PRs
    prs = data.get('github', {}).get('prs_authored', [])
    pr_projects = analyzer.analyze_prs(prs)
    
    # Analyze calendar events
    events = data.get('calendar', {}).get('events', [])
    event_projects = analyzer.analyze_calendar_events(events)
    
    # Merge projects
    projects = analyzer.merge_projects(pr_projects, event_projects)
    
    print(f"✓ Identified {len(projects)} projects")
    
    return projects


def main():
    """Main execution function."""
    # Load configuration
    base_dir = Path(__file__).parent.parent
    config_path = base_dir / "config" / "team_config.json"
    
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Load secrets from environment variables
    import os
    if not config.get('github_pat'):
        config['github_pat'] = os.getenv('GITHUB_PAT', '')
    if not config.get('slack_token'):
        config['slack_token'] = os.getenv('SLACK_TOKEN', '')
    
    print(f"\n{'='*60}")
    print(f"Year Review Data Collection - {config['year']}")
    print(f"Team: {config['team_name']}")
    print(f"{'='*60}\n")
    
    # Setup directories
    data_dir = base_dir / "data" / "raw"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    templates_dir = base_dir / "templates"
    output_dir = base_dir / "docs"  # GitHub Pages serves from /docs folder
    
    # Collect data for each member
    all_members_data = []
    
    for member in config['members']:
        member_key = member.get('github') or member['name'].lower().replace(' ', '_')
        
        # Check if data already exists
        data_file = data_dir / f"{member_key}_data.json"
        projects_file = data_dir / f"{member_key}_projects.json"
        
        if data_file.exists() and projects_file.exists():
            print(f"\nUsing cached data for {member['name']}")
            with open(data_file) as f:
                data = json.load(f)
            with open(projects_file) as f:
                projects = json.load(f)
        else:
            # Collect fresh data
            data = collect_member_data(member, config)
            projects = analyze_projects(member, data, config)
            
            # Save data
            data_file.write_text(json.dumps(data, indent=2, default=str))
            projects_file.write_text(json.dumps(projects, indent=2, default=str))
        
        all_members_data.append({
            'member': member,
            'data': data,
            'projects': projects
        })
    
    # Generate pages
    print(f"\n{'='*60}")
    print("Generating HTML pages...")
    print(f"{'='*60}\n")
    
    generator = PageGenerator(templates_dir, output_dir)
    members_for_team_page = []
    
    for member_data in all_members_data:
        member = member_data['member']
        data = member_data['data']
        projects = member_data['projects']
        
        # Calculate stats
        stats = {
            'prs_authored': len(data.get('github', {}).get('prs_authored', [])),
            'prs_reviewed': len(data.get('github', {}).get('prs_reviewed', [])),
            'slack_messages': data.get('slack', {}).get('total_messages', 0),
            'calendar_events': data.get('calendar', {}).get('total_events', 0),
            'projects': len(projects)
        }
        
        # Generate summary with topics
        result = generator._generate_summary(projects, stats)
        if len(result) == 3:
            line1, line2, topics = result
        else:
            line1, line2 = result
            topics = []
        
        # Generate individual page
        filename = generator.generate_individual_page(member, data, projects, config['year'])
        
        members_for_team_page.append({
            'name': member['name'],
            'email': member.get('slack') or member.get('github', ''),
            'filename': f"{filename}.html",
            'summary_line1': line1,
            'summary_line2': line2,
            'topics': topics,
            'stats': stats
        })
    
    # Generate team page
    generator.generate_team_page(members_for_team_page, config['team_name'], config['year'])
    
    print(f"\n{'='*60}")
    print("✓ Data collection and page generation complete!")
    print(f"{'='*60}\n")
    print(f"Generated pages are in: {output_dir}")
    print(f"Team summary: {output_dir / 'index.html'}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

