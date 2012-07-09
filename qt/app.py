# Created By: Virgil Dupras
# Created On: 2011-06-21
# Copyright 2011 Hardcoded Software (http://www.hardcoded.net)
# 
# This software is licensed under the "GPL v3" License as described in the "LICENSE" file, 
# which should be included with this package. The terms are also available at 
# http://www.hardcoded.net/licenses/gplv3_license

import os
import os.path as op
import logging

from PyQt4.QtCore import SIGNAL, QUrl, QCoreApplication, QProcess
from PyQt4.QtGui import QDesktopServices, QMessageBox, QFileDialog

from hscommon.trans import tr
from hscommon.plat import ISLINUX
from jobprogress import job
from jobprogress.qt import Progress
from qtlib.about_box import AboutBox
from qtlib.app import Application as ApplicationBase
from qtlib.reg import Registration
from qtlib.util import createActions

from core.app import App, JOBID2TITLE
from .main_window import MainWindow
from .preferences import Preferences
from .plat import HELP_PATH

class PdfMasher(ApplicationBase):
    LOGO_NAME = 'logo'
    
    def __init__(self):
        appdata = str(QDesktopServices.storageLocation(QDesktopServices.DataLocation))
        if not op.exists(appdata):
            os.makedirs(appdata)
        # For basicConfig() to work, we have to be sure that no logging has taken place before this call.
        logging.basicConfig(filename=op.join(appdata, 'debug.log'), level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s')
        ApplicationBase.__init__(self)
        self._setupActions()
        self.prefs = Preferences()
        self.prefs.load()
        self.model = App(view=self)
        self.mainWindow = MainWindow(app=self)
        self.aboutBox = AboutBox(self.mainWindow, self)
        self.reg = Registration(self.model)
        self._progress = Progress(self.mainWindow)
        
        self.connect(self, SIGNAL('applicationFinishedLaunching()'), self.applicationFinishedLaunching)
        self.connect(QCoreApplication.instance(), SIGNAL('aboutToQuit()'), self.applicationWillTerminate)
        self._progress.finished.connect(self.jobFinished)
    
    #--- Public
    def askForRegCode(self):
        self.reg.ask_for_code()
    
    #--- Private
    def _setupActions(self):
        ACTIONS = [
            ('actionLoadProject', 'Ctrl+Shift+O', '', tr("Load Project"), self.loadProjectTriggered),
            ('actionSaveProject', 'Ctrl+S', '', tr("Save Project"), self.saveProjectTriggered),
            ('actionQuit', 'Ctrl+Q', '', tr("Quit"), self.quitTriggered),
            ('actionShowHelp', 'F1', '', tr("PDfMasher Help"), self.showHelpTriggered),
            ('actionAbout', '', '', tr("About dupeGuru"), self.showAboutBoxTriggered),
            ('actionRegister', '', '', tr("Register dupeGuru"), self.registerTriggered),
            ('actionCheckForUpdate', '', '', tr("Check for Update"), self.checkForUpdateTriggered),
            ('actionOpenDebugLog', '', '', tr("Open Debug Log"), self.openDebugLogTriggered),
        ]
        createActions(ACTIONS, self)
        
        if ISLINUX:
            self.actionCheckForUpdate.setVisible(False) # This only works on Windows
    
    #--- Event Handling
    def applicationFinishedLaunching(self):
        self.model.initial_registration_setup()
        self.mainWindow.show()
    
    def applicationWillTerminate(self):
        self.prefs.save()
    
    def jobFinished(self, jobid):
        self.model._job_completed(jobid)
    
    def loadProjectTriggered(self):
        self.model.load_project("/Users/hsoft/Desktop/pdfmashertest.masherproj")
    
    def saveProjectTriggered(self):
        self.model.save_project("/Users/hsoft/Desktop/pdfmashertest.masherproj")
    
    def checkForUpdateTriggered(self):
        QProcess.execute('updater.exe', ['/checknow'])
    
    def openDebugLogTriggered(self):
        appdata = QDesktopServices.storageLocation(QDesktopServices.DataLocation)
        debugLogPath = op.join(appdata, 'debug.log')
        url = QUrl.fromLocalFile(debugLogPath)
        QDesktopServices.openUrl(url)
    
    def quitTriggered(self):
        self.mainWindow.close()
    
    def registerTriggered(self):
        self.reg.ask_for_code()
    
    def showAboutBoxTriggered(self):
        self.aboutBox.show()
    
    def showHelpTriggered(self):
        url = QUrl.fromLocalFile(op.abspath(op.join(HELP_PATH, 'index.html')))
        QDesktopServices.openUrl(url)
    
    #--- model --> view
    @staticmethod
    def open_path(path):
        url = QUrl.fromLocalFile(path)
        QDesktopServices.openUrl(url)
    
    @staticmethod
    def reveal_path(path):
        PdfMasher.open_path(op.dirname(path))
    
    def open_url(self, url):
        url = QUrl(url)
        QDesktopServices.openUrl(url)
    
    def setup_as_registered(self):
        self.prefs.registration_code = self.model.registration_code
        self.prefs.registration_email = self.model.registration_email
        # self.mainWindow.actionRegister.setVisible(False)
        self.aboutBox.registerButton.hide()
        self.aboutBox.registeredEmailLabel.setText(self.prefs.registration_email)
    
    def show_message(self, msg):
        QMessageBox.information(self.mainWindow, '', msg)
    
    def start_job(self, jobid, func, *args):
        title = JOBID2TITLE[jobid]
        try:
            j = self._progress.create_job()
            args = tuple([j] + list(args))
            self._progress.run(jobid, title, func, args=args)
        except job.JobInProgressError:
            msg = "A previous action is still hanging in there. You can't start a new one yet. Wait a few seconds, then try again."
            QMessageBox.information(self.mainWindow, "Action in progress", msg)
    
    def get_default(self, key):
        return self.prefs.get_value(key)
    
    def set_default(self, key, value):
        self.prefs.set_value(key, value)
    
    def show_fairware_nag(self, prompt):
        reg = Registration(self.model)
        reg.show_fairware_nag(prompt)
    
    def show_demo_nag(self, prompt):
        reg = Registration(self.model)
        reg.show_demo_nag(prompt)
    
    def query_load_path(self, prompt):
        # XXX Eventually, the line below won't be hardcoded
        files = ';;'.join(["PDF file (*.pdf)", "All Files (*.*)"])
        return QFileDialog.getOpenFileName(self.mainWindow, prompt, '', files)
    
    def query_save_path(self, prompt, allowed_exts):
        myfilters = ["{0} file (*.{0})".format(ext) for ext in allowed_exts]
        files = ';;'.join(myfilters+ ["All Files (*.*)"])
        return QFileDialog.getSaveFileName(self.mainWindow, prompt, '', files)
    
