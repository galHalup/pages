#!/usr/bin/env python3
"""
HTML page generator for year review.
Generates individual and team summary pages from collected data.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader, select_autoescape


class PageGenerator:
    def __init__(self, templates_dir: Path, output_dir: Path):
        self.templates_dir = templates_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def _calculate_monthly_prs(self, prs: List[Dict]) -> Dict[str, int]:
        """Calculate PR count per month."""
        monthly = {}
        for pr in prs:
            if pr.get('created_at'):
                try:
                    dt = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                    month_key = dt.strftime('%Y-%m')
                    monthly[month_key] = monthly.get(month_key, 0) + 1
                except:
                    pass
        return monthly
    
    def _generate_github_urls(self, username: str, year: int) -> Dict[str, str]:
        """Generate GitHub search URLs."""
        base_url = "https://github.com/pulls"
        return {
            'prs': f"{base_url}?q=is%3Apr+author%3A{username}+created%3A{year}-01-01..{year}-12-31",
            'reviews': f"{base_url}?q=is%3Apr+reviewed-by%3A{username}+created%3A{year}-01-01..{year}-12-31"
        }
    
    def _generate_summary(self, projects: Dict[str, Dict], stats: Dict) -> tuple:
        """Generate 2-line summary for team member card."""
        bullets = []
        topics = set()
        
        # Extract topics from projects
        for project in projects.values():
            tags = project.get('tags', [])
            topics.update(tags)
            category = project.get('category', '')
            if category:
                topics.add(category)
        
        # Generate bullets
        if stats.get('prs_authored', 0) > 0 or stats.get('prs_reviewed', 0) > 0:
            bullets.append(f"Authored {stats.get('prs_authored', 0)} PRs and reviewed {stats.get('prs_reviewed', 0)} in {2025}")
        
        if stats.get('calendar_events', 0) > 0:
            # Get top topic from calendar events
            top_topic = list(topics)[0] if topics else "Meetings"
            bullets.append(f"Attended {stats.get('calendar_events', 0)} meetings focusing on {top_topic}")
        
        line1 = bullets[0] if bullets else "Active contributor throughout the year."
        line2 = bullets[1] if len(bullets) > 1 else "Focused on team collaboration and code quality."
        
        return line1, line2, list(topics)[:3]  # Return top 3 topics
    
    def generate_individual_page(self, member: Dict, data: Dict, projects: Dict[str, Dict], year: int):
        """Generate individual team member page."""
        template = self.env.get_template('individual_template.html')
        
        # Calculate stats
        prs_authored = len(data.get('github', {}).get('prs_authored', []))
        prs_reviewed = len(data.get('github', {}).get('prs_reviewed', []))
        slack_messages = data.get('slack', {}).get('total_messages', 0)
        calendar_events = data.get('calendar', {}).get('total_events', 0)
        
        stats = {
            'prs_authored': prs_authored,
            'prs_reviewed': prs_reviewed,
            'slack_messages': slack_messages,
            'calendar_events': calendar_events,
            'projects': len(projects)
        }
        
        # Generate GitHub URLs
        github_urls = self._generate_github_urls(member.get('github', ''), year) if member.get('github') else {}
        
        # Organize projects by quarter
        import sys
        from pathlib import Path
        if str(Path(__file__).parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).parent))
        from project_analyzer import ProjectAnalyzer
        
        analyzer = ProjectAnalyzer({})  # Empty keywords, already analyzed
        quarters = analyzer.organize_by_quarter(projects)
        
        # Calculate monthly PRs
        monthly_prs = self._calculate_monthly_prs(data.get('github', {}).get('prs_authored', []))
        max_prs = max(monthly_prs.values()) if monthly_prs else 1
        
        # Ensure all months are present
        for month_num in range(1, 13):
            month_key = f"{year}-{month_num:02d}"
            if month_key not in monthly_prs:
                monthly_prs[month_key] = 0
        
        # Sort months
        monthly_prs = dict(sorted(monthly_prs.items()))
        
        # Calculate Q1-Q4 PRs
        q_prs = {'Q1': 0, 'Q2': 0, 'Q3': 0, 'Q4': 0}
        for pr in data.get('github', {}).get('prs_authored', []):
            if pr.get('created_at'):
                try:
                    dt = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                    q_num = (dt.month - 1) // 3 + 1
                    q_key = f"Q{q_num}"
                    if q_key in q_prs:
                        q_prs[q_key] += 1
                except:
                    pass
        
        # Group projects by topic and select top 4 per quarter
        quarters_by_topic = {}
        for quarter_key, quarter_projects in quarters.items():
            if not quarter_projects:
                quarters_by_topic[quarter_key] = {}
                continue
                
            # Group by category/topic
            by_topic = {}
            for project in quarter_projects:
                topic = project.get('category', 'feature')
                if topic not in by_topic:
                    by_topic[topic] = []
                by_topic[topic].append(project)
            
            # Select top 4 projects per topic, then top 4 topics
            top_projects_by_topic = {}
            for topic, topic_projects in by_topic.items():
                # Sort by number of PRs + events
                sorted_topic = sorted(topic_projects, 
                                    key=lambda p: len(p.get('prs', [])) + len(p.get('events', [])), 
                                    reverse=True)
                top_projects_by_topic[topic] = sorted_topic[:4]
            
            # Get top 4 topics
            sorted_topics = sorted(top_projects_by_topic.items(), 
                                 key=lambda x: sum(len(p.get('prs', [])) + len(p.get('events', [])) 
                                                  for p in x[1]), 
                                 reverse=True)[:4]
            quarters_by_topic[quarter_key] = dict(sorted_topics)
        
        # Render template
        html = template.render(
            name=member['name'],
            year=year,
            stats=stats,
            github_prs_url=github_urls.get('prs', '#'),
            github_reviews_url=github_urls.get('reviews', '#'),
            quarters=quarters_by_topic,  # Use grouped by topic
            q_prs=q_prs,
            monthly_prs=monthly_prs,
            max_prs=max_prs,
            generation_date=datetime.now().strftime('%B %Y')
        )
        
        # Write to file
        filename = member.get('github') or member['name'].lower().replace(' ', '_')
        if not filename or filename == 'None':
            filename = member['name'].lower().replace(' ', '_')
        output_file = self.output_dir / f"{filename}.html"
        output_file.write_text(html)
        print(f"Generated: {output_file}")
        
        return filename
    
    def generate_team_page(self, members_data: List[Dict], team_name: str, year: int):
        """Generate team summary page."""
        template = self.env.get_template('team_template.html')
        
        # Calculate team stats
        team_stats = {
            'total_prs': sum(m.get('stats', {}).get('prs_authored', 0) for m in members_data),
            'total_reviews': sum(m.get('stats', {}).get('prs_reviewed', 0) for m in members_data),
            'total_slack_messages': sum(m.get('stats', {}).get('slack_messages', 0) for m in members_data),
            'total_projects': sum(m.get('stats', {}).get('projects', 0) for m in members_data),
            'team_size': len(members_data)
        }
        
        # Generate team summary
        total_contributions = team_stats['total_prs'] + team_stats['total_reviews']
        team_summary = (
            f"The {team_name} had an outstanding year in {year}, with {team_stats['total_prs']} pull requests "
            f"authored and {team_stats['total_reviews']} reviews completed across {team_stats['total_projects']} "
            f"major projects. The team demonstrated exceptional collaboration and technical excellence throughout the year."
        )
        
        # Render template
        html = template.render(
            team_name=team_name,
            year=year,
            team_stats=team_stats,
            team_summary=team_summary,
            members=members_data,
            generation_date=datetime.now().strftime('%B %Y')
        )
        
        # Write to file
        output_file = self.output_dir / "index.html"
        output_file.write_text(html)
        print(f"Generated: {output_file}")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    templates_dir = base_dir / "templates"
    output_dir = base_dir / "generated"
    data_dir = base_dir / "data" / "raw"
    
    generator = PageGenerator(templates_dir, output_dir)
    
    # Load config
    config_path = base_dir / "config" / "team_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Load collected data
    members_data = []
    for member in config['members']:
        data_file = data_dir / f"{member.get('github', member['name'].lower().replace(' ', '_'))}_data.json"
        if data_file.exists():
            with open(data_file) as f:
                data = json.load(f)
            
            # Load projects
            projects_file = data_dir / f"{member.get('github', member['name'].lower().replace(' ', '_'))}_projects.json"
            projects = {}
            if projects_file.exists():
                with open(projects_file) as f:
                    projects = json.load(f)
            
            # Calculate stats
            stats = {
                'prs_authored': len(data.get('github', {}).get('prs_authored', [])),
                'prs_reviewed': len(data.get('github', {}).get('prs_reviewed', [])),
                'slack_messages': data.get('slack', {}).get('total_messages', 0),
                'calendar_events': data.get('calendar', {}).get('total_events', 0),
                'projects': len(projects)
            }
            
            # Generate summary
            line1, line2 = generator._generate_summary(projects, stats)
            
            # Generate individual page
            filename = generator.generate_individual_page(member, data, projects, config['year'])
            
            members_data.append({
                'name': member['name'],
                'filename': f"{filename}.html",
                'summary_line1': line1,
                'summary_line2': line2,
                'stats': stats
            })
    
    # Generate team page
    generator.generate_team_page(members_data, config['team_name'], config['year'])
    print("All pages generated successfully!")

