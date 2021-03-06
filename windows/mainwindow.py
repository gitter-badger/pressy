import threading
import time
import webbrowser

import pressy.qtall as qt
import pressy.utils as ut

from pressy.windows.feedtree import FeedTree
from pressy.windows.explorer import FeedExplorer
from pressy.document.feed import Document
from pressy.server import run_server

class MainWin(qt.QMainWindow):

    windows = []
    @classmethod
    def createWindow(cls):
        win = cls()
        win.show()
        cls.windows.append(win)

    def __init__(self):
        super(MainWin, self).__init__()
        self.document = Document()

        self.setup()
        self.make_toolbar()
        
        self.make_connection()

        self.setWindowTitle("Pressy")
        self.progress_bar = qt.QProgressBar(self.statusBar())
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        policy = qt.QSizePolicy(qt.QSizePolicy.Fixed,
                                qt.QSizePolicy.Fixed)
        def sizeHint():
            return qt.QSize(200, 18)
        self.progress_bar.sizeHint = sizeHint
        self.progress_bar.setSizePolicy(policy)

        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()
        self.setWindowIcon(ut.getIcon("main"))

        self.run_ser()

    def make_toolbar(self):
        a = ut.makeAction
        self.actions = {
                'feed.add':
                a(self, "add a feed", "&Add a feed",
                  self.slot_add_feed,
                  icon = "feed_add", key = None), 
                'link.jump':
                a(self, "jump to browser", "&Jump",
                  self.slot_jump_browser,
                  icon = "jump", key = None),
                }

        # create toolbar
        web_toolBar = qt.QToolBar("web toolbar", self)
        web_toolBar.addAction(self.web_view.pageAction(qt.QtWebKit.QWebPage.Back))
        web_toolBar.addAction(self.web_view.pageAction(qt.QtWebKit.QWebPage.Forward))
        web_toolBar.addAction(self.web_view.pageAction(qt.QtWebKit.QWebPage.Reload))
        web_toolBar.addAction(self.web_view.pageAction(qt.QtWebKit.QWebPage.Stop))

        self.add_new_edit = qt.QLineEdit(web_toolBar)
        ori_event_handler = self.add_new_edit.keyPressEvent
        def keyPressEvent(e):
            key = e.key()
            if key == qt.Qt.Key_Enter or key == qt.Qt.Key_Return:
                self.add_new_edit.emit(qt.SIGNAL("set_link"), unicode(self.add_new_edit.text())) 
            else:
                ori_event_handler(e)
        self.add_new_edit.keyPressEvent = keyPressEvent
        web_toolBar.insertWidget(None, self.add_new_edit)
        ut.addToolbarActions(web_toolBar, self.actions, ('feed.add', 'link.jump'))
        self.addToolBar(qt.Qt.TopToolBarArea, web_toolBar)
        self.web_view.urlChanged.connect(self.slot_set_url) 

    def setup(self):
        self.splitter = qt.QSplitter(self)
        self.splitter.setHandleWidth(1)
        self.feed_tree = FeedTree(self.document, self)
        self.splitter.addWidget(self.feed_tree)

        self.web_view = FeedExplorer(self.document, self)
        self.web_view.page().setLinkDelegationPolicy(qt.QWebPage.DelegateAllLinks)
        self.connect(self.web_view, qt.SIGNAL("linkClicked(QUrl)"), lambda url:
                self.web_view.setUrl(url))

        self.holder = qt.QFrame(self)
        self.holder.setFrameStyle(qt.QFrame.Panel | qt.QFrame.Raised)
        def enterEvent(e):
            self.holder.hide()
            self.feed_tree.show()
            self.splitter.setSizes(self.tree_splitter_sizes)

        self.holder.enterEvent = enterEvent
        self.holder.hide()
        self.splitter.addWidget(self.holder)

        self.splitter.addWidget(self.web_view)

        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 3)
        self.setCentralWidget(self.splitter)
        
        self.connect(self.splitter, qt.SIGNAL("splitterMoved(int, int)"),
                self.slot_save_size)


        self.web_view.titleChanged.connect(self.adjustTitle)
        self.web_view.loadProgress.connect(self.setProgress)
        self.web_view.loadFinished.connect(self.finishLoading)

    def make_connection(self):
        self.connect(self, qt.SIGNAL("add_feed"), self.feed_tree.slot_add_feed)
        self.connect(self.web_view, qt.SIGNAL("update_unread_num"), self.feed_tree.slotUpdateUnread)
        self.connect(self.feed_tree, qt.SIGNAL("show_update_msg"), self.slot_show_update_msg)
        self.connect(self.add_new_edit, qt.SIGNAL("set_link"), self.slot_set_link)

    def slot_save_size(self):
        if self.feed_tree.isVisible():
            self.tree_splitter_sizes = self.splitter.sizes()

    def slot_set_link(self, link):
        if not link.startswith("http:"):
            link = "http://" + link
        self.web_view.setUrl(qt.QUrl(link))

    def slot_set_url(self, url):
        url = url.toString()
        self.add_new_edit.setText(url)

    def slot_show_update_msg(self):
        msg = "%d feeds updated, %d itmes updated."%(self.document.update_feeds, self.document.update_items)
        self.statusBar().showMessage(msg, msecs=10000)

    def slot_add_feed(self):
        """ read the feed link from line edit and add it to document"""
        feed_link = unicode(self.add_new_edit.text())
        if not feed_link:
            qt.QMessageBox.information(
                    self, "Info - Pressy",
                    "Please put the feed link to left edit.")
            return 
        # get the html
        page = self.web_view.page()
        frame = page.currentFrame()
        html = frame.toHtml()
        if self.document.add_feed(feed_link, html):
            qt.QMessageBox.warning(
                    self, "Error - Pressy",
                    "Can't parse this feed \n%s"%feed_link)
        else:
            self.emit(qt.SIGNAL("add_feed"), self.document.feedlist[-1])

    def setProgress(self, p ):
        """ set the page loading progress"""
        if self.progress_bar.isHidden():
            self.progress_bar.show()
        self.web_view.progress = p
        self.progress_bar.setValue(p)
        if p == 100:
            self.finishLoading()

    def finishLoading(self):
        self.web_view.progress = 100
        self.progress_bar.setValue(self.web_view.progress)
        self.progress_bar.hide()

    def adjustTitle(self):
        self.setWindowTitle("Pressy - " + self.web_view.title())
        self.web_view.emit(qt.SIGNAL("update_unread_num"))

    def run_ser(self):
        """ run the bottle server"""
        thread = threading.Thread(target=run_server, args=(self.document,))
        thread.setDaemon(True)
        thread.start()

    def slot_jump_browser(self):
        webbrowser.open(self.add_new_edit.text())

    def showEvent(self, e):
        """ set the link editor focus """
        self.activateWindow()
        self.add_new_edit.setFocus()
        super(MainWin, self).showEvent(e)
        self.tree_splitter_sizes = self.splitter.sizes()

    def closeEvent(self, e):
        """ save feeds before close window"""
        while self.document.update:
            time.sleep(0.5)
        self.document.save_feeds()
        e.accept()
