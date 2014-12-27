# Created By: Virgil Dupras
# Created On: 2011-06-12
# Copyright 2013 Hardcoded Software (http://www.hardcoded.net)
#
# This software is licensed under the "GPL v3" License as described in the "LICENSE" file,
# which should be included with this package. The terms are also available at
# http://www.hardcoded.net/licenses/gplv3_license

from xml.etree import ElementTree as ET
from pdfminer.pdfparser import PDFSyntaxError

from hscommon.notify import Broadcaster
from hscommon.geometry import Rect
from hscommon.trans import tr

from .const import ElementState
from .pdf import extract_text_elements_from_pdf, Page, TextElement
from . import __appname__
from .gui.element_table import ElementTable
from .gui.opened_file_label import OpenedFileLabel
from .gui.page_controller import PageController
from .gui.build_pane import BuildPane
from .gui.edit_pane import EditPane

class JobType:
    LoadPDF = 'job_load_pdf'


JOBID2TITLE = {
    JobType.LoadPDF: tr("Reading PDF"),
}

class App(Broadcaster):
    #--- model -> view calls:
    # open_path(path)
    # reveal_path(path)
    # start_job(j, *args)
    # query_load_path(prompt, allowed_exts) --> str_path
    # query_save_path(prompt, allowed_exts) --> str_path

    PROMPT_NAME = __appname__
    NAME = PROMPT_NAME
    DEMO_LIMITATION = "will only be able load the 10 first pages of a PDF"

    def __init__(self, view):
        Broadcaster.__init__(self)
        self.view = view
        self.current_path = None
        self._hide_ignored = False
        self.selected_elements = set()
        self.pages = []
        self.elements = []
        self.last_file_was_invalid = False

        self.element_table = ElementTable(self)
        self.opened_file_label = OpenedFileLabel(self)
        self.page_controller = PageController(self)
        self.build_pane = BuildPane(self)
        self.edit_pane = EditPane(self)

    #--- Protected
    def _job_completed(self, jobid):
        # Must be called by subclasses when they detect that an async job is completed.
        if jobid == JobType.LoadPDF:
            if not self.last_file_was_invalid:
                self.notify('file_opened')
                self.opened_file_label.refresh()
                self.notify('elements_changed')
            else:
                self.view.show_message("This file is not a PDF.")

    #--- Public (Internal)
    def select_elements(self, elements):
        if elements == self.select_elements:
            return
        self.selected_elements = elements
        self.notify('elements_selected')

    #--- Public (API)
    def open_path(self, path):
        self.view.open_path(path)

    def reveal_path(self, path):
        self.view.reveal_path(path)

    def change_state_of_selected(self, newstate):
        for element in self.selected_elements:
            if newstate == ElementState.Title:
                if element.state == ElementState.Title:
                    element.title_level += 1
                    if element.title_level > 6:
                        element.title_level = 1
                else:
                    element.title_level = 1
            element.state = newstate
        self.notify('elements_changed')

    def load_pdf(self):
        path = self.view.query_load_path("Select a PDF to work with", ['pdf'])
        if not path:
            return

        def do(j):
            self.last_file_was_invalid = False
            try:
                self.pages, self.elements = extract_text_elements_from_pdf(path, j)
                self.current_path = path
            except PDFSyntaxError:
                self.last_file_was_invalid = True

        self.view.start_job(JobType.LoadPDF, do)

    def load_project(self):
        path = self.view.query_load_path("Select a PdfMasher project to load", ['masherproj'])
        if not path:
            return

        def str2rect(s):
            elems = s.split(' ')
            assert len(elems) == 4
            return Rect(*map(float, elems))

        root = ET.parse(path).getroot()
        self.pages = []
        for page_elem in root.iter('page'):
            attrs = page_elem.attrib
            width = float(attrs['width'])
            height = float(attrs['height'])
            self.pages.append(Page(width, height))
        self.elements = []
        for elem_elem in root.iter('element'):
            attrs = elem_elem.attrib
            rect = str2rect(attrs['rect'])
            fontsize = float(attrs['fontsize'])
            text = attrs['text']
            elem = TextElement(rect, fontsize, text)
            elem.page = int(attrs['page'])
            elem.order = int(attrs['order'])
            elem.state = attrs['state']
            elem.title_level = int(attrs['title_level'])
            self.elements.append(elem)
        self.current_path = root.attrib['pdfpath']
        self.notify('file_opened')
        self.opened_file_label.refresh()
        self.notify('elements_changed')

    def save_project(self):
        path = self.view.query_save_path("Select a PdfMasher project to save to", ['masherproj'])
        if not path:
            return

        def rect2str(r):
            return "{} {} {} {}".format(*r)

        root = ET.Element('pdfmasher-project')
        root.set('pdfpath', self.current_path)
        for page in self.pages:
            page_elem = ET.SubElement(root, 'page')
            page_elem.set('width', str(page.width))
            page_elem.set('height', str(page.height))
        for elem in self.elements:
            elem_elem = ET.SubElement(root, 'element')
            elem_elem.set('page', str(elem.page))
            elem_elem.set('order', str(elem.order))
            elem_elem.set('rect', rect2str(elem.rect))
            elem_elem.set('fontsize', str(elem.fontsize))
            elem_elem.set('text', elem.text)
            elem_elem.set('state', elem.state)
            elem_elem.set('title_level', str(elem.title_level))
        tree = ET.ElementTree(root)
        with open(path, 'wb') as fp:
            tree.write(fp, encoding='utf-8')

    #--- Properties
    @property
    def hide_ignored(self):
        return self._hide_ignored

    @hide_ignored.setter
    def hide_ignored(self, value):
        self._hide_ignored = value
        self.notify('elements_changed')

