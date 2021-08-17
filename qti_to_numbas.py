"""
QTI to Numbas
by Christian Lawson-Perfect
© 2021 Newcastle University
"""


from bs4 import BeautifulSoup
from pathlib import Path
import json
import zipfile
import argparse

def tag_contents(e):
    """
        Return the contents of a tag as a string.
    """
    return ''.join(str(x) for x in e.contents)
    
class QTI2Numbas(object):
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


def load_question_bank(path):
    """
        Load a bank of questions from a file containing an `assessmentTest` tag, and return a description of a Numbas exam.

        Parameter:
            path - a Path pointing to the XML file defining the question bank.

        Returns:
            A dictionary representing a Numbas exam.
    """
    with path.open() as f:
        bank = BeautifulSoup(f,'xml')

    test = bank.find('assessmentTest')

    exam = {
        'name': test['title'],
        'question_groups': [],
    }

    for section in bank.find_all('assessmentSection'):
        group = {'name': section['title'], 'questions': []}
        exam['question_groups'].append(group)
        for ref in section.find_all('assessmentItemRef'):
            fname = ref['href']
            p = path.parent / fname
            with p.open() as f:
                t = BeautifulSoup(f,'xml')
            q = QTI2Numbas(t)
            group['questions'].append(q.question)

    return exam

def write_exam(exam,outfile):
    """
        Write a Numbas exam to a .exam file.

        Parameters:
            exam - A dictionary describing the exam.
            outfile - The Path of the file to write.
    """

    outfile.parent.mkdir(parents=True,exist_ok=True)
    with open(outfile,'w') as f:
        f.write('// Numbas version: exam_results_page_options\n')
        f.write(json.dumps(exam))    
    print("Created {}".format(outfile))

def convert_package(root, outpath):
    """
        Convert a package and make Numbas .exam files.

        Parameters:
            root - The Path to the package to convert.
            outpath - The Path to the directory to put .exam files in.
    """

    with (root / 'imsmanifest.xml').open() as f:
        manifest = BeautifulSoup(f, 'xml')
        
        
    for b in manifest.select('manifest > resources > resource[type="imsqti_test_xmlv2p1"]'):
        exam = load_question_bank(root / b['href'])
        write_exam(exam, outpath / (exam['name']+'.exam'))

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Convert a QTI 2.1 item package to Numbas .exam files')
    parser.add_argument('input',help='The zip file or directory to convert.')
    parser.add_argument('-o','--output',default='.',help='The directory to put .exam files in. Defaults to the current working directory.')

    args = parser.parse_args()

    outpath = Path(args.output)

    root = Path(args.input)
    if root.suffix == '.zip':
        root = zipfile.Path(root)

    convert_package(root, outpath)
