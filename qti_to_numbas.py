"""
QTI to Numbas
by Christian Lawson-Perfect
© 2021 Newcastle University
"""


import argparse
from bs4 import BeautifulSoup
import json
from pathlib import Path, PurePath
import re
import shutil
from slugify import slugify
import sys
import zipfile

import canvas_qti_1_2
import blackboard_qti_2_1

class IMS_to_Numbas(object):
    def __init__(self,root):
        self.root = root
        self.exams = []

    def new_exam(self):
        exam = {
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
        self.exams.append(exam)
        return exam
        
    def read_canvas_assessment_meta(self, path, exam):
        with path.open() as f:
            meta = BeautifulSoup(f, 'xml')
            
        exam['name'] = meta.find('title').string
        exam['metadata']['description'] = meta.find('description').string or ''
        show_answers = meta.find('show_correct_answers').string == 'true'
        exam['feedback']['showactualmark'] = show_answers
        exam['feedback']['showanswerstate'] = show_answers
        exam['feedback']['reviewshowexpectedanswer'] = show_answers
        
    def process(self):
        with (self.root / 'imsmanifest.xml').open() as f:
            manifest = BeautifulSoup(f,'xml')

        resources = manifest.select_one('manifest resources')

        for r in resources.find_all('resource'):
            if r['type'] == 'imsqti_xmlv1p2':
                fileinfo = r.find('file')
                
                exam = self.new_exam()
                canvas_qti_1_2.QTI_1_2_to_Numbas(exam, self.root / fileinfo['href'])
                
                dep = r.find('dependency')
                if dep:
                    rd = resources.find('resource',identifier=dep['identifierref'])
                    if rd:
                        if rd['type'] == 'associatedcontent/imscc_xmlv1p1/learning-application-resource':
                            fileinfo = rd.find('file')
                            href = fileinfo['href']
                            self.read_canvas_assessment_meta(self.root / href, exam)
            elif r['type'] == 'imsqti_test_xmlv2p1':
                blackboard_qti_2_1.load_question_bank(self.new_exam(), self.root / r['href'])

        num_exams = len(self.exams)
        print(f"Converted {num_exams} exams." if num_exams !=0 else 'Converted 1 exam.')

    def write_exams(self, outpath):
        for exam in self.exams:
            self.write_exam(exam, outpath / (slugify(exam['name'])+'.exam'))
                            
    def write_exam(self, exam, outfile):
        """
            Write a Numbas exam to a .exam file.

            Parameters:
                exam - A JSON description of a Numbas exam.
                outfile - The Path of the file to write.
        """

        if isinstance(outfile,Path):
            outfile.parent.mkdir(parents=True,exist_ok=True)
            f = open(outfile,'w')
        else:
            f = outfile

        if 'resources' in exam and len(exam['resources']) > 0:
            resourced = outfile.with_suffix('') / 'resources'
            resourced.mkdir(parents=True, exist_ok=True)
            nresources = []
            for r in exam['resources']:
                if r.startswith('/'):
                    r = r[1:]
                p = PurePath(r)
                source = self.root / p
                out = resourced / source.name
                if isinstance(source, zipfile.Path):
                    source.root.extract(source.at, resourced)
                else:
                    shutil.copy(source, out)
                nresources.append( (source.name, str(out.resolve())) )

            exam['resources'] = nresources

        f.write('// Numbas version: exam_results_page_options\n')
        f.write(json.dumps(exam,indent=2))    
        if isinstance(outfile,Path):
            f.close()
            print("Created {}".format(outfile))

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Convert a QTI item package to Numbas .exam files')
    parser.add_argument('input',help='The zip file or directory to convert.')
    parser.add_argument('-o','--output',default='.',help='The name of the .exam file to write. Defaults to the current directory.')

    args = parser.parse_args()

    root = Path(args.input)
    if root.suffix == '.zip':
        root = zipfile.Path(root)

    converter = IMS_to_Numbas(root)
    converter.process()

    outpath = Path(args.output)

    converter.write_exams(outpath)
