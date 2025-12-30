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
        if not projects:
            return "Active contributor throughout the year.", "Focused on team collaboration and code quality."
        
        # Get top projects
        sorted_projects = sorted(projects.values(), 
                                key=lambda p: len(p.get('prs', [])) + len(p.get('events', [])), 
                                reverse=True)
        top_projects = sorted_projects[:3]
        
        project_names = [p['name'] for p in top_projects]
        
        if len(project_names) >= 2:
            line1 = f"Led {project_names[0]} and contributed to {project_names[1]}."
            if len(project_names) >= 3:
                line2 = f"Also worked on {project_names[2]} and {stats.get('prs_authored', 0)}+ other contributions."
            else:
                line2 = f"Made {stats.get('prs_authored', 0)}+ contributions across multiple initiatives."
        elif len(project_names) == 1:
            line1 = f"Led {project_names[0]} initiative."
            line2 = f"Made {stats.get('prs_authored', 0)}+ contributions throughout the year."
        else:
            line1 = f"Active contributor with {stats.get('prs_authored', 0)}+ PRs."
            line2 = "Focused on code quality and team collaboration."
        
        return line1, line2
    
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
        
        # Render template
        html = template.render(
            name=member['name'],
            year=year,
            stats=stats,
            github_prs_url=github_urls.get('prs', '#'),
            github_reviews_url=github_urls.get('reviews', '#'),
            quarters=quarters,
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

