import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'skills/document-translation/scripts'))
import agent_packets


class AgentPacketTests(unittest.TestCase):
    def test_boundary_context_skips_page_furniture_without_merging_source(self):
        def block(uid, text, kind='paragraph', role=None, did='D1', page=1):
            b = {'type': kind, 'source': {'document_id': did, 'page': page},
                 'units': [{'id': uid, 'source': text, 'translations': {}}]}
            if role:
                b['presentation'] = {'role': role}
            return b

        content = {'blocks': [
            block('u1', 'This activates the self-'),
            block('m1', '99', role='metadata'),
            block('c1', 'Figure 2.', role='caption', page=2),
            block('u2', 'resetting circuit.', page=2),
            block('u3', 'Another document.', did='D2', page=1),
        ]}
        items = agent_packets.prepare(content, 'ja', ['faithful', 'interpretive'], True, lambda s: [s])
        self.assertEqual([u['source'] for u in items], [b['units'][0]['source'] for b in content['blocks']])
        context = items[0]['context']
        self.assertEqual(context['neighbors_for_context_only']['next']['id'], 'm1')
        self.assertEqual(context['narrative_neighbors_for_context_only']['next']['id'], 'u2')
        self.assertEqual(context['narrative_neighbors_for_context_only']['next']['locator']['page'], 2)
        self.assertNotIn('next', items[3]['context']['narrative_neighbors_for_context_only'])
        self.assertTrue(items[0]['source_checks']['possible_boundary_fragment']['ends_hyphen'])
        self.assertTrue(items[3]['source_checks']['possible_boundary_fragment']['starts_lowercase'])

    def test_claim_and_abbreviation_prompts_do_not_rewrite_source(self):
        text = 'Simulation results validate the proposed design; resilience is necessary. Power-delay product (PDP) may decrease.'
        checks = agent_packets.source_checks(text)
        self.assertIn('validate', checks['scope_cues'])
        self.assertIn('necessary', checks['scope_cues'])
        self.assertIn('may', checks['scope_cues'])
        self.assertIn('Simulation', checks['study_cues'])
        self.assertTrue(any('Power-delay product (PDP)' in s for s in checks['explicit_abbreviation_context']))
        self.assertFalse(checks['possible_boundary_fragment']['ends_without_terminal'])

    def test_fragment_edges_are_visible_without_completion_or_source_mutation(self):
        text = 'For the proposed assembly, the dimensions and the complexity of'
        checks = agent_packets.source_checks(text)['possible_boundary_fragment']
        self.assertTrue(checks['ends_without_terminal'])
        self.assertEqual(checks['source_prefix'],text)
        self.assertEqual(checks['source_suffix'],text)
        self.assertTrue(checks['source_suffix'].endswith('complexity of'))
        other = agent_packets.source_checks('each component were considered.')['possible_boundary_fragment']
        self.assertTrue(other['starts_lowercase'])
        self.assertNotIn('complexity',other['source_prefix'])

    def test_scope_and_quantity_context_preserves_exact_capability_and_signs(self):
        text = 'Injecting 1 and −1 fC can validate the proposed circuit. We plan a later experiment.'
        checks = agent_packets.source_checks(text)
        cues = checks['claim_scope_context']
        self.assertIn('can', [x['cue'] for x in cues])
        self.assertIn('proposed', [x['cue'] for x in cues])
        self.assertIn('plan', [x['cue'] for x in cues])
        self.assertIn('−1 fC', [x['cue'] for x in checks['quantity_context']])
        for item in cues + checks['quantity_context']:
            self.assertEqual(text[slice(*item['offset'])], item['cue'])
            self.assertEqual(text[slice(*item['context_offset'])], item['context'])
        self.assertIn('not an experiment already performed', checks['context_contract'])

    def test_review_context_is_bounded_without_truncating_source(self):
        text = ' '.join('We may test −5 ns.' for _ in range(80))
        checks = agent_packets.source_checks(text)
        self.assertEqual(len(checks['claim_scope_context']), 16)
        self.assertEqual(len(checks['quantity_context']), 24)
        self.assertTrue(all(len(x['context']) <= 190 for x in checks['claim_scope_context']))
        self.assertEqual(checks['possible_boundary_fragment']['source_suffix'], text[-96:])
