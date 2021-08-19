from bs4 import BeautifulSoup
import re

class QTIException(Exception):
    pass

class Question(object):
    score_scale = 1
    marks = None
    
    def __init__(self, item, question, marks):
        self.item = item
        self.question = question
        self.marks = marks
        self.process()
        
    def process(self):
        item = self.item
        part = self.part = {}
        self.question['parts'].append(part)
        meta = self.meta = {}
        
        self.question['name'] = item['title']

        # Get metadata informatin (Canvas-specific?)
        for d in item.select('qtimetadata qtimetadatafield'):
            self.meta[d.find('fieldlabel').string] = d.find('fieldentry').string
        
        # Total marks
        marks = float(meta['points_possible'])
        part['marks'] = self.marks if self.marks is not None and marks>0 else marks

        # Multiplier for scores in the outcome processing
        decvar = item.select_one('resprocessing outcomes decvar[varname="SCORE"]')
        if decvar:
            self.score_scale = (part['marks'] if part['marks']>0 else 1) / float(decvar['maxvalue'])        
        
        # Prompt
        prompt = item.select_one('presentation material mattext').string
        part['prompt'] = prompt
        
        # Question-type specific behaviour
        question_types = {
            'multiple_choice_question': self.multiple_choice_question,
            'true_false_question': self.multiple_choice_question,
            'short_answer_question': self.short_answer_question,
            'fill_in_multiple_blanks_question': self.fill_in_multiple_blanks_question,
            'multiple_answers_question': self.multiple_answers_question,
            'multiple_dropdowns_question': self.multiple_dropdowns_question,
            'matching_question': self.matching_question,
            'numerical_question': self.numerical_question,
            'calculated_question': self.calculated_question,
            'essay_question': self.essay_question,
            'text_only_question': self.text_only_question,
        }
        
        question_type = meta['question_type']
        if question_type in question_types:
            question_types[question_type]()
        else:
            raise QTIException(f"Unrecognised question type: {question_type}")
        
        return part
    
    def get_choices(self):
        """
            Get the list of choices and corresponding feedback strings for a 1_n_2 or m_n_2 part.
        """
        item = self.item
        part = self.part
        
        choices = {}
        for r in item.select('presentation response_lid render_choice response_label'):
            ident = r['ident']
            choice = {
                'content': r.find('mattext').string or '',
                'distractor': '',
                'marks': 0,
            }
            choices[ident] = choice
            
        feedback = {}
        for fb in item.find_all('itemfeedback'):
            feedback[fb['ident']] = fb.find('mattext').string
        
        return choices, feedback

    def multiple_choice_question(self):
        item = self.item
        part = self.part
        
        part['type'] = '1_n_2'
        
        choices, feedback = self.get_choices()
        
        for rc in item.select('resprocessing respcondition'):
            v = rc.select_one('conditionvar varequal[respident="response1"]')
            if not v:
                continue
            choice_ident = v.string
            choice = choices[choice_ident]
            d = rc.find('displayfeedback',feedbacktype='Response')
            sv = rc.find('setvar',action="Set",varname='SCORE')
            if sv:
                choice['marks'] = float(sv.string)*self.score_scale
            elif d:
                choice['distractor'] = feedback[d['linkrefid']]

        choices = list(choices.values())
        part['choices'] = [c['content'] for c in choices]
        part['distractors'] = [c['distractor'] for c in choices]
        part['matrix'] = [c['marks'] for c in choices]
        
    def short_answer_question(self):
        item = self.item
        part = self.part
        part['type'] = 'patternmatch'
        
        rc = item.select_one('resprocessing respcondition')
        answers = [v.string for v in rc.select('conditionvar varequal')]

        part['answer'] = answers[0]
        if len(answers)>0:
            part['alternatives'] = []
            part['useAlternativeFeedback'] = True
            for answer in answers[1:]:
                alt = {
                    'type': 'patternmatch',
                    'marks': part['marks'],
                }
                alt['answer'] = answer
                part['alternatives'].append(alt)
                
    def get_gaps(self):
        """
            Get a list of gaps from the prompt text.
        """
        part = self.part
        
        part['type'] = 'gapfill'
        
        re_gap = re.compile(r'\[([^\]]*)\]')

        prompt_soup = BeautifulSoup(part['prompt'], 'html.parser')
        gapnames = list(set(re_gap.findall(' '.join(prompt_soup.strings))))
        for s in prompt_soup.find_all(string=True):
            s.replace_with(re_gap.sub(lambda m: '[['+str(gapnames.index(m[1]))+']]', s))
        part['prompt'] = str(prompt_soup)
        
        gapdict = {name: {'marks': part['marks'] / len(gapnames)} for name in gapnames}
        part['gaps'] = [gapdict[n] for n in gapdict]
        
        return gapdict

    def fill_in_multiple_blanks_question(self):
        item = self.item
        part = self.part
        
        gapdict = self.get_gaps()
        
        for gap in gapdict.values():
            gap['type'] = 'patternmatch'
        
        for r in item.select('presentation response_lid'):
            gapname = r.select_one('material mattext').string
            gap = gapdict[gapname]
            answers = [v.string for v in r.select('render_choice response_label material mattext')]
            gap['answer'] = answers[0]
            if len(answers)>0:
                gap['alternatives'] = []
                gap['useAlternativeFeedback'] = True
                for answer in answers[1:]:
                    alt = {
                        'type': 'patternmatch',
                        'marks': gap['marks'],
                    }
                    alt['answer'] = answer
                    gap['alternatives'].append(alt)
        
    def multiple_answers_question(self):
        item = self.item
        part = self.part
        
        part['type'] = 'm_n_2'
        part['markingMethod'] = 'all-or-nothing'
        
        choices, feedback = self.get_choices()

        for b in item.select('resprocessing respcondition conditionvar > and > varequal'):
            choice = choices[b.string]
            choice['marks'] = 1
        
        choices = list(choices.values())
        part['choices'] = [c['content'] for c in choices]
        part['distractors'] = [c['distractor'] for c in choices]
        part['matrix'] = [c['marks'] for c in choices]

    def multiple_dropdowns_question(self):
        item = self.item
        part = self.part
        
        gapdict = self.get_gaps()

        responses = {}
        for c in item.select('resprocessing respcondition'):
            v = c.select_one('respcondition conditionvar varequal')
            responses[v['respident']] = v.string
            
        for r in item.select('presentation response_lid'):
            gapname = r.select_one('material mattext').string
            gap = gapdict[gapname]
            gap['type'] = '1_n_2'
            gap['displayType'] = 'dropdownlist'
            choices = {}
            for rl in r.select('render_choice response_label'):
                ident = rl['ident']
                text = rl.select_one('material mattext').string
                choices[ident] = {
                    'content': text, 
                    'marks': gap['marks'] if ident == responses[r['ident']] else 0,
                }
                
            choices = list(choices.values())
            gap['choices'] = [c['content'] for c in choices]
            gap['matrix'] = [c['marks'] for c in choices]
            

    def matching_question(self):
        item = self.item
        part = self.part

        part['type'] = 'm_n_x'
        part['displayType'] = 'radiogroup'
        
        part['choices'] = [c.string for c in item.select('presentation response_lid > material > mattext')]
        
        choice_idents = []
        answer_idents = []
        part['answers'] = []
        
        for rl in item.select('presentation > response_lid'):
            ident = rl['ident']
            content = rl.material.string
            choice_idents.append(ident)
            part['answers'] = [l.material.mattext.string for l in rl.select('render_choice > response_label')]
            answer_idents = [l['ident'] for l in rl.select('render_choice > response_label')]
            
        matrix = part['matrix'] = [[0]*len(part['answers']) for i in part['choices']]
        for c in item.select('resprocessing respcondition'):
            v = c.conditionvar.varequal
            choice_ident = v['respident']
            answer_ident = v.string
            score = float(c.setvar.string)
            matrix[choice_idents.index(choice_ident)][answer_idents.index(answer_ident)] = score * self.score_scale

    def numerical_question(self):
        item = self.item
        part = self.part

        part['type'] = 'numberentry'
        
        alternatives = item.select('resprocessing > respcondition')

        ps = [part]
        if len(alternatives)>1:
            part['alternatives'] = [{'type': 'numberentry', 'marks': part['marks']} for i in alternatives[1:]]
            part['useAlternativeFeedback'] = True
            ps += part['alternatives']
        
        for p,c in zip(ps,alternatives):
            if c.find('vargt'):
                p['precisionType'] = 'sigfig'
                answer = c.select_one('conditionvar > or > varequal').string
                p['precision'] = len(answer.replace('.',''))
                p['minValue'] = p['maxValue'] = answer
            else:
                p['minValue'] = c.find('vargte').string
                p['maxValue'] = c.find('varlte').string
                
    def define_variable(self, name, definition):
        self.question['variables'][name] = {
            'name': name.strip(),
            'definition': definition,
        }

    def calculated_question(self):
        item = self.item
        part = self.part

        part['type'] = 'numberentry'
        
        re_var = re.compile(r'\[([^\]]*)\]')
        prompt_soup = BeautifulSoup(part['prompt'], 'html.parser')
        for s in prompt_soup.find_all(string=True):
            bits = re.split(r'(\\[()])',s)
            ns = ''
            for i in range(len(bits))[::4]:
                sub = bits[i:i+4]
                plain = sub[0]
                o = re.sub(r'\[([^\]]*)\]',r'{\1}',plain)
                if len(sub)>1:
                    _, l, tex, r = sub
                    o = o + l + re.sub(r'\[([^\]]*)\]',r'\\var{\1}',tex) + r
                ns += o
            s.replace_with(ns)
            
        part['prompt'] = str(prompt_soup)
        
        self.question['variables'] = {}
        for v in item.select('calculated > vars > var'):
            name = v['name']
            minvalue = v.find('min').string
            maxvalue = v.find('max').string
            step = v['scale']
            self.define_variable(name, f'random({minvalue}..{maxvalue}#10^-{step})')
            

        tolerance_string = item.select_one('calculated > answer_tolerance').string
        if tolerance_string[-1] == '%':
            tolerance_string = tolerance_string[:-1]
            lower = f' * (1 - {tolerance_string}/100)'
            higher = f' * (1 + {tolerance_string}/100)'
        else:
            lower = f' - {tolerance_string}'
            higher = f' + {tolerance_string}'

        dp = int(item.select_one('calculated > formulas')['decimal_places'])
        part['precision'] = dp
        part['precisionType'] = 'dp'
        for f in item.select('calculated > formulas > formula'):
            formula = f.string
            if '=' in formula:
                name, val = formula.split('=')
                self.define_variable(name, val)
            else:
                part['minValue'] = formula + lower
                part['maxValue'] = formula + higher

    def essay_question(self):
        self.part['type'] = 'patternmatch'
        self.part['answer'] = ''

    def text_only_question(self):
        self.part['type'] = 'information'

    
class QTI_1_2_to_Numbas(object):
    def __init__(self, exam, path):
        self.exam = exam
        self.path = path
        self.process()
        
    def process(self):
        with self.path.open() as f:
            doc = BeautifulSoup(f, 'xml')
            
        assessment = doc.find('assessment')
        self.exam['name'] = assessment['title']
        
        sections = assessment.find_all('section')
        for section in sections:
            self.section(section)
            
    def section(self, section):
        question_group = {
            'name': section.get('title',''),
            'questions': [],
        }

        items = section.find_all('item',recursive=False)

        points_per_item = 1
        
        ordering = section.find('selection_ordering',recursive=False)
        if ordering:
            pickQuestions = question_group['pickQuestions'] = int(ordering.find('selection_number').string)
            if pickQuestions < len(items):
                question_group['pickingStrategy'] = 'random-subset'
            po = ordering.find('points_per_item')
            if po:
                points_per_item = float(po.string)

        for item in items:
            q = self.item(item, points_per_item)
            question_group['questions'].append(q)
            
        self.exam['question_groups'].append(question_group)

    def item(self, item, marks):
        question = {
            'name': '',
            'statement': '',
            'parts': [],
        }
        
        Question(item, question, marks)
        
        return question
