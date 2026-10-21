"""Small front page and expandable evidence for the efficiency analysis."""
import html
import json

from .report_efficiency import AXES
from .report_graphics import efficiency_plot


def efficiency_sections(data, root, table):
    result = data['research_efficiency']
    sections = ['<h1>Research efficiency</h1>',
                '<p>How much model quality did each strategy achieve for the resources it spent?</p>',
                '<h2>Computed summary</h2>']
    sections += ['<p>' + html.escape(text) + '</p>' for text in result['summary']]
    sections.append('<p><a href="report-summary.txt">Plain-text summary</a> · '
                    '<a href="research-efficiency.json">Computed results and methodology</a> · '
                    '<a href="resource-trajectories.json">Individual trajectories</a> · '
                    '<a href="report-provenance.json">Input provenance</a></p>')
    for cohort in result['cohorts']:
        sections.append(f"<h2>Cohort {cohort['id']}: quality at comparable budgets</h2>")
        sections.append(efficiency_plot(data, cohort, root))
        sections.append('<details><summary>Budget measurements, improvement, and individual trajectories</summary>')
        sections.append('<p>Improvement is signed so positive means better. Each run starts from its own observed quality '
                        'at the shared lower budget. AUC is the area under that improvement curve divided by the interval width; '
                        'it is average improvement in native metric units, not a percentage or a fraction of possible quality. '
                        'The starting models may differ. Initial spending remains in the absolute budget; no free starting model is assumed. '
                        'For experiments, the discrete average uses attempts after the start through the endpoint.</p>')
        sections.append(table(['Resource', 'Start', 'End', 'Strategy', 'All runs', 'Start quality', 'End quality',
                               'End quality SD', 'Improvement', 'Mean improvement AUC', 'AUC SD'],
            [[AXES[a], facts['start'], facts['budget'], group, g['n'], g['baseline'], g['quality'],
              g['quality_sd'], g['improvement'], g['mean_improvement_auc'], g['auc_sd']]
             for a, facts in cohort['axes'].items() for group, g in facts['groups'].items()]))
        sections.append('<p>SD describes observed repeats, not uncertainty across tasks or data splits. '
                        'Unavailable rows are not replaced with successful-run averages. Full trajectories below have different '
                        'end budgets and do not constitute equal-budget comparisons.</p>')
        sections.append(efficiency_plot(data, cohort, root, individual=True))
        sections.append('<details><summary>Exact cohort membership, settings, and per-run calculations</summary><pre>' +
                        html.escape(json.dumps(cohort, indent=2, ensure_ascii=False)) + '</pre></details></details>')
    sections.append('<details><summary>Resource evidence coverage and method</summary>')
    sections.append(table(['Run', 'Resource', 'Known prefix end', 'Scored observations', 'Evidence limit'],
        [[r['run_id'], AXES[a], c['end'], len(c['points']), c['reason'] or 'No recorded resource gap']
         for r in data['runs'] for a, c in r['resource_trajectories'].items()]))
    sections.append('<pre>' + html.escape(json.dumps({'method': result['method'], 'excluded_runs': result['excluded_runs']},
                                                   indent=2, ensure_ascii=False)) + '</pre></details>')
    if data['warnings']:
        sections.append(f"<p><strong>Evidence limitations:</strong> {len(data['warnings'])} loading or comparability note(s) "
                        'are listed in the supporting evidence. Interpret the computed differences with those limits.</p>')
    return sections
