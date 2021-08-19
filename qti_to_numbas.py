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
import re
import sys

import canvas_qti_1_2
import blackboard_qti_2_1

class IMS_to_Numbas(object):
    def __init__(self,root):
        self.root = root
        self.exam = {
            'name': '', 
            'metadata': {
                'description': '',
                'licence': '',
            },
            'feedback': {
                'showactualmark': True,
                'showtotalmark': True,
                'showanswerstate': True,
                'reviewshowexpectedanswer': True,
            },
            'question_groups': [],
        }
        
    def read_canvas_assessment_meta(self, path):
        with path.open() as f:
            meta = BeautifulSoup(f, 'xml')
            
        self.exam['name'] = meta.find('title').string
        self.exam['metadata']['description'] = meta.find('description').string or ''
        show_answers = meta.find('show_correct_answers').string == 'true'
        self.exam['feedback']['showactualmark'] = show_answers
        self.exam['feedback']['showanswerstate'] = show_answers
        self.exam['feedback']['reviewshowexpectedanswer'] = show_answers
        
    def process(self):
        with (self.root / 'imsmanifest.xml').open() as f:
            manifest = BeautifulSoup(f,'xml')

        resources = manifest.select_one('manifest resources')

        for r in resources.find_all('resource'):
            if r['type'] == 'imsqti_xmlv1p2':
                file = r.find('file')
                
                canvas_qti_1_2.QTI_1_2_to_Numbas(self.exam, self.root / file['href'])
                
                dep = r.find('dependency')
                if dep:
                    rd = resources.find('resource',identifier=dep['identifierref'])
                    if rd:
                        if rd['type'] == 'associatedcontent/imscc_xmlv1p1/learning-application-resource':
                            file = rd.find('file')
                            href = file['href']
                            self.read_canvas_assessment_meta(self.root / href)
            elif r['type'] == 'imsqti_test_xmlv2p1':
                blackboard_qti_2_1.load_question_bank(self.exam, self.root / r['href'])
                            
    def write_exam(self, outfile):
        """
            Write a Numbas exam to a .exam file.

            Parameters:
                outfile - The Path of the file to write.
        """

        if isinstance(outfile,Path):
            outfile.parent.mkdir(parents=True,exist_ok=True)
            f = open(outfile,'w')
        else:
            f = outfile
        f.write('// Numbas version: exam_results_page_options\n')
        f.write(json.dumps(self.exam,indent=2))    
        if isinstance(outfile,Path):
            f.close()
            print("Created {}".format(outfile))

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Convert a QTI item package to Numbas .exam files')
    parser.add_argument('input',help='The zip file or directory to convert.')
    parser.add_argument('-o','--output',default=None,help='The name of the .exam file to write. Defaults to printing to STDOUT.')

    args = parser.parse_args()

    root = Path(args.input)
    if root.suffix == '.zip':
        root = zipfile.Path(root)

    converter = IMS_to_Numbas(root)
    converter.process()

    outpath = Path(args.output) if args.output is not None else sys.stdout

    converter.write_exam(outpath)
