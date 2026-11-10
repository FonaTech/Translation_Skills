"""Typography-only model inputs require explicit native document witnesses."""
import copy
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import inference_text as inference


def block(identifier,text,kind='paragraph',document='D1'):
    return {'id':identifier,'type':kind,'source':{'document_id':document,'page':1},
            'units':[{'id':identifier+'-U','source':text}]}


def test_heading_case_has_native_same_document_word_witnesses():
    content={'blocks':[block('H','III. GENETIC ALGORITHM','heading'),
                       block('P','The genetic algorithm is described in the source.') ]}
    before=copy.deepcopy(content)
    inference.prepare(content)
    unit=content['blocks'][0]['units'][0]
    assert unit['source']==before['blocks'][0]['units'][0]['source']
    assert unit['protected_identifiers'][0]['source']=='III.'
    prompt,changes=inference.prompt_text('GENETIC ALGORITHM',unit['inference_context'])
    assert prompt=='Genetic algorithm' and len(changes)==2
    assert changes[0]['witness']['unit_id']=='P-U'
    assert all(ch['before'].casefold()==ch['after'].casefold() for ch in changes)


def test_acronyms_body_code_other_document_and_unwitnessed_capitals_are_preserved():
    content={'blocks':[block('H','IV. FPGA MEMORY','heading'),
                       block('P','The memory uses an FPGA.'),
                       block('X','memory fpga','paragraph','D2')]}
    inference.prepare(content)
    unit=content['blocks'][0]['units'][0]
    prompt,changes=inference.prompt_text('FPGA MEMORY',unit['inference_context'])
    assert prompt=='FPGA memory'
    assert [ch['before'] for ch in changes]==['MEMORY']
    assert 'inference_context' not in content['blocks'][1]['units'][0]
    assert inference.prompt_text('UNKNOWN',unit['inference_context'])==('UNKNOWN',[])
    assert inference.prompt_text('GENETIC ALGORITHM')==('GENETIC ALGORITHM',[])


def test_prepare_rebuilds_context_and_preserves_existing_literal_intervals():
    content={'blocks':[block('H','III. GENETIC ALGORITHM','heading'),
                       block('P','The genetic algorithm is used.') ]}
    unit=content['blocks'][0]['units'][0]
    unit['protected_identifiers']=[{'start':0,'end':4,'source':'III.','kind':'existing'}]
    inference.prepare(content);inference.prepare(content)
    assert len(unit['protected_identifiers'])==1
    content['blocks'].pop()
    inference.prepare(content)
    assert 'inference_context' not in unit
