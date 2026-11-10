"""Independent rejection tests for merged native table ownership. MIT."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/document-translation/scripts'))
import table_topology


def fixture():
    return {'id': 'table', 'header_rows': 2,
            'rows': [['stub', 'group', None], [None, 'a', 'b'],
                     ['shared', 'a1', 'b1'], [None, 'a2', 'b2']],
            'units': [{'id': uid, 'source_cell': span} for uid, span in [
                ('stub', {'rowspan': 2}), ('group', {'colspan': 2}),
                ('a', {}), ('b', {}), ('shared', {'rowspan': 2}),
                ('a1', {}), ('b1', {}), ('a2', {}), ('b2', {})]]}


def test_valid_multi_level_header_and_vertical_data_merge():
    block = fixture()
    original = copy.deepcopy(block)
    assert table_topology.errors(block) == []
    assert block == original


def test_covered_cell_cannot_own_independent_text():
    block = fixture()
    block['rows'][1][0] = 'a'
    assert table_topology.errors(block)[0]['code'] == 'table-cell-topology'


def test_missing_owner_and_out_of_bounds_or_cross_section_spans():
    for span in [{}, {'rowspan': 20}, {'rowspan': 3}, {'rowspan': True}]:
        block = fixture()
        block['units'][0]['source_cell'] = span
        assert table_topology.errors(block)
    block = fixture()
    block['rows'][0][0] = 'unknown'
    assert table_topology.errors(block)


def test_non_rectangular_merged_table_is_rejected():
    block = fixture()
    block['rows'][-1].pop()
    assert table_topology.errors(block)
