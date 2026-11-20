"""Fictional, idempotent demo fixtures; no imported prospects or customer outcomes."""
from .store import DomainError


def seed(store):
    if not store.demo:
        raise DomainError('Demo seeding requires an explicitly separate demo workspace.')
    state=store.snapshot()
    if not state['config']['segment']:
        store.save_config({
            'version':state['config']['version'],'business_name':'Example Studio',
            'offer':'Illustrative scoped workflow automation pilot. Actual scope and terms are not configured.',
            'segment':'Fictional operations teams used to demonstrate the control room.',
            'priority_exclusions':'Business has closed permanently.',
            'approved_claims':['Example Studio explores scoped workflow automation pilots; actual workflow and access need validation.'],
            'qualification_rubric':'Demo only: confirm workflow relevance, a process owner, and a useful next step.',
        })
    existing={a['domain'] for a in state['accounts']}
    for name,domain,segment,claim in [
        ('Atlas Supply','atlas-supply.example','Distribution','Fictional case: quote requests arrive with varying specifications.'),
        ('Northline Logistics','northline.example','Logistics','Fictional case: shipment updates cross an operations-to-customer handoff.'),
        ('Forma Packaging','forma-packaging.example','Packaging','Fictional case: artwork revisions require review before production.'),
    ]:
        if domain not in existing:
            store.add_account({'name':name,'domain':domain,'segment':segment,'claim':claim,'source':'Fictional demonstration scenario; not a real company finding.'})
