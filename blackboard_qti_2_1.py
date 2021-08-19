from bs4 import BeautifulSoup

def tag_contents(e):
    """
        Return the contents of a tag as a string.
    """
    return ''.join(str(x) for x in e.contents)
    
class QTI_2_1_to_Numbas(object):
    currentPart = None
    finishedPart = True

    def __init__(self, tree):
        """
            Convert a QTI assessment item to a Numbas question.

            Parameter:
                tree - A BeatifulSoup4 document containing an `assessmentItem` tag.
            
            After processing, `self.question` is a description of a Numbas question.
        """
        self.tree = tree
        self.question = {
            'statement': '',
            'parts': []
        }
        self.process()
        
    def process(self):
        item = self.tree.find('assessmentItem')
        self.question['name'] = item['title']
        body = self.tree.find('itemBody')
        for c in body:
            if self.finishedPart:
                self.new_part()
            if c.name == 'div':
                self.currentPart['prompt'] = tag_contents(c)
            elif c.name == 'choiceInteraction':
                choices = c.find_all('simpleChoice')
                choice_text = [tag_contents(ch) for ch in choices]
                responseIdentifier = c['responseIdentifier']
                responseDeclaration = item.find('responseDeclaration',identifier=responseIdentifier)
                if responseDeclaration is None:
                    print(t.prettify())
                correct_response = responseDeclaration.select('correctResponse > value')[0].string
                matrix = [1 if ch['identifier'] == correct_response else 0 for ch in choices]
                self.currentPart['type'] = '1_n_2'
                self.currentPart['choices'] = choice_text
                self.currentPart['matrix'] = matrix
                self.currentPart['shuffleChoices'] = c['shuffle'] == 'true'
                self.finishedPart = True

    def new_part(self):
        self.currentPart = {'prompt': '', 'type': 'information'}
        self.finishedPart = False
        self.question['parts'].append(self.currentPart)


def load_question_bank(exam, path):
    """
        Load a bank of questions from a file containing an `assessmentTest` tag, and return a description of a Numbas exam.

        Parameter:
            exam - A dict describing the exam, to be filled in.
            path - A Path pointing to the XML file defining the question bank.

        Returns:
            A dictionary representing a Numbas exam.
    """
    with path.open() as f:
        bank = BeautifulSoup(f,'xml')

    test = bank.find('assessmentTest')

    exam['name'] = test['title']
    
    for section in bank.find_all('assessmentSection'):
        group = {'name': section['title'], 'questions': []}
        exam['question_groups'].append(group)
        for ref in section.find_all('assessmentItemRef'):
            fname = ref['href']
            p = path.parent / fname
            with p.open() as f:
                t = BeautifulSoup(f,'xml')
            q = QTI_2_1_to_Numbas(t)
            group['questions'].append(q.question)

    return exam