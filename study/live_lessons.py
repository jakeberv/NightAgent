"""Read-only lesson notebook built from accepted memory snapshots."""
from copy import deepcopy

from rich.console import Console, Group
from rich.panel import Panel


class LessonFeed:
    def __init__(self):
        self.entries = {}

    def update(self, lessons, *, source=None):
        # Mirror the bounded register, preserving revision metadata for unchanged
        # entries. Rendering must never feed changes back into agent memory.
        lessons = lessons[-12:]
        present = {lesson['id'] for lesson in lessons}
        self.entries = {key: value for key, value in self.entries.items() if key in present}
        for lesson in lessons:
            previous = self.entries.get(lesson['id'])
            if previous and previous['lesson'] == lesson:
                continue
            self.entries.pop(lesson['id'], None)
            self.entries[lesson['id']] = {
                'lesson': deepcopy(lesson), 'source': source or 'agent',
                'revision': previous['revision'] + 1 if previous else 1,
                'change': ('Superseded' if lesson['status'] == 'superseded' else
                           'Updated' if previous else 'New')}

    @property
    def latest(self):
        return next(reversed(self.entries.values()), None)


def visible(state):
    return bool(state.config.get('lesson_memory') or state.lessons.entries)


def evidence_label(entry):
    ids = list(dict.fromkeys(item['trial_id'] for item in entry['lesson'].get('evidence', [])))
    return entry['source'].capitalize() + (' · trial ' if len(ids) == 1 else ' · trials ') + ', '.join(map(str, ids))


def focus_lesson(state, width, *, lines=2):
    from .focus import fitting_summary
    entry = state.lessons.latest
    if not entry:
        return 'Lessons · agent takeaways\nNo lessons recorded yet.'
    lesson = entry['lesson']
    summary = fitting_summary(lesson['summary'], width, lines, 'Full lesson saved in lessons.json.')
    return (f"Lessons · {entry['change']} · {lesson['status']}\n" + summary + '\n' + evidence_label(entry))


def lesson_panel(state, *, width, height):
    from .focus import fitting_summary
    from .terminal import text
    inner = max(1, width - 4)
    console = Console(width=width)
    rows, used, shown = [], 0, 0
    entries = list(reversed(state.lessons.entries.values()))
    def lines(value):
        return max(1, len(text(value).wrap(console, inner)))
    if not entries:
        rows.append(text('No lessons recorded yet.', 'dim'))
    # Prioritize complete prose; use spare space to point to remaining entries.
    available = max(0, height - 2)
    for entry in entries:
        lesson = entry['lesson']
        label = f"{entry['change']} · {lesson['status']} · {lesson['id']}"
        citation = evidence_label(entry)
        summary = fitting_summary(lesson['summary'], inner, max(1, available - used - lines(label) - lines(citation)),
                                  'Full lesson saved in lessons.json.')
        block = '\n'.join((label, summary, citation))
        if used + lines(block) > available:
            break
        style = 'dim' if lesson['status'] == 'superseded' else 'yellow' if lesson['status'] == 'inconclusive' else 'cyan'
        rows.append(text(block, style))
        used += lines(block)
        shown += 1
        scope = fitting_summary(lesson.get('scope', ''), inner - len('Scope: '), 2, '')
        if scope and used + lines('Scope: ' + scope) <= available:
            rows.append(text('Scope: ' + scope, 'dim'))
            used += lines('Scope: ' + scope)
    if shown < len(entries):
        footer = f'{len(entries) - shown} more in lessons.json.'
        if used + lines(footer) <= height - 2:
            rows.append(text(footer, 'dim'))
    return Panel(Group(*rows), title=text(f'Lessons · agent takeaways ({len(entries)})'),
                 subtitle=text('Full notebook: lessons.json'),
                 border_style='cyan', padding=(0, 1), height=height)
