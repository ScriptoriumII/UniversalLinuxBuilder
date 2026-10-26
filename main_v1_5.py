import sys, json, re, urllib.request, urllib.parse
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QComboBox,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QLabel,QCheckBox,QFileDialog,QMessageBox,QTextEdit,QMenu,QAbstractItemView,QSplitter,QFrame)

VERSION='1.5'
DISTROS={'Debian':['trixie','bookworm'],'Fedora':['43','42'],'Slackware':['15.0','current'],'Gentoo':['stable','testing'],'Arch Linux':['rolling']}
DESKTOPS=['Aucun','GNOME','KDE Plasma','Xfce','Budgie']
KERNELS={'Arch Linux':{'Stable':['linux'],'LTS':['linux-lts'],'Hardened':['linux-hardened']},'Debian':{'Stable':['linux-image-amd64']},'Fedora':{'Stable':['kernel']},'Gentoo':{'Stable':['sys-kernel/gentoo-kernel']},'Slackware':{'Stable':['kernel-generic']}}
PROFILES={
'Arch Linux':{'GNOME':(['gnome','gdm','networkmanager','mesa','xdg-desktop-portal-gnome'],'gdm.service','Wayland'),'KDE Plasma':(['plasma','sddm','konsole','dolphin','networkmanager','mesa','xdg-desktop-portal-kde'],'sddm.service','Wayland'),'Xfce':(['xfce4','xfce4-goodies','lightdm','lightdm-gtk-greeter','xorg-server','networkmanager','mesa'],'lightdm.service','X11'),'Budgie':(['budgie-desktop','gdm','networkmanager','mesa'],'gdm.service','Wayland')},
'Debian':{'GNOME':(['gnome-core','gdm3','network-manager'],'gdm3.service','Wayland'),'KDE Plasma':(['kde-plasma-desktop','sddm','network-manager'],'sddm.service','Wayland'),'Xfce':(['xfce4','xfce4-terminal','lightdm','xserver-xorg','network-manager'],'lightdm.service','X11'),'Budgie':(['budgie-desktop','lightdm','xserver-xorg','network-manager'],'lightdm.service','X11')},
'Fedora':{'GNOME':(['gnome-shell','gnome-session','gdm','NetworkManager'],'gdm.service','Wayland'),'KDE Plasma':(['plasma-desktop','plasma-workspace','sddm','NetworkManager'],'sddm.service','Wayland'),'Xfce':(['xfce4-session','xfce4-panel','xfwm4','xfdesktop','lightdm','xorg-x11-server-Xorg','NetworkManager'],'lightdm.service','X11'),'Budgie':(['budgie-desktop','gdm','NetworkManager'],'gdm.service','Wayland')},
'Gentoo':{'GNOME':(['gnome-base/gnome','gnome-base/gdm','net-misc/networkmanager'],'gdm.service','Wayland'),'KDE Plasma':(['kde-plasma/plasma-meta','x11-misc/sddm','net-misc/networkmanager'],'sddm.service','Wayland'),'Xfce':(['xfce-base/xfce4-meta','x11-misc/lightdm','x11-base/xorg-server','net-misc/networkmanager'],'lightdm.service','X11'),'Budgie':(['gnome-extra/budgie-desktop','gnome-base/gdm','net-misc/networkmanager'],'gdm.service','Wayland')},
'Slackware':{'KDE Plasma':(['kde/plasma-workspace','kde/plasma-desktop','kde/sddm'],'sddm','X11'),'Xfce':(['xfce/xfce4-session','xfce/xfce4-panel','xfce/xfwm4'],'xdm','X11')}}
AUDIO={'Arch Linux':{'PipeWire':['pipewire','wireplumber','pipewire-pulse','pipewire-alsa'],'PulseAudio':['pulseaudio'],'ALSA':['alsa-utils']},'Debian':{'PipeWire':['pipewire','wireplumber','pipewire-pulse'],'PulseAudio':['pulseaudio'],'ALSA':['alsa-utils']},'Fedora':{'PipeWire':['pipewire','wireplumber','pipewire-pulseaudio'],'PulseAudio':['pulseaudio'],'ALSA':['alsa-utils']},'Gentoo':{'PipeWire':['media-video/pipewire','media-video/wireplumber'],'PulseAudio':['media-sound/pulseaudio'],'ALSA':['media-sound/alsa-utils']},'Slackware':{'PipeWire':['pipewire','wireplumber'],'PulseAudio':['pulseaudio'],'ALSA':['alsa-utils']}}
EXTRA={'Arch Linux':{'base':['base','systemd','linux-firmware','pciutils','usbutils'],'wifi':['iwd'],'bluetooth':['bluez','bluez-utils'],'printing':['cups'],'firmware':['linux-firmware'],'calamares':['calamares'],'X11':['xorg-server'],'Wayland':['wayland']},'Debian':{'base':['systemd-sysv','udev','pciutils','usbutils'],'wifi':['wpasupplicant'],'bluetooth':['bluez'],'printing':['cups'],'firmware':['firmware-linux-free'],'calamares':['calamares'],'X11':['xserver-xorg'],'Wayland':['libwayland-client0']},'Fedora':{'base':['systemd','pciutils','usbutils'],'wifi':['NetworkManager-wifi'],'bluetooth':['bluez'],'printing':['cups'],'firmware':['linux-firmware'],'calamares':[],'X11':['xorg-x11-server-Xorg'],'Wayland':['wayland']},'Gentoo':{'base':['sys-apps/systemd','sys-apps/pciutils'],'wifi':['net-wireless/iwd'],'bluetooth':['net-wireless/bluez'],'printing':['net-print/cups'],'firmware':['sys-kernel/linux-firmware'],'calamares':[],'X11':['x11-base/xorg-server'],'Wayland':['dev-libs/wayland']},'Slackware':{'base':['a/sysvinit','a/udev'],'wifi':['n/wpa_supplicant'],'bluetooth':['n/bluez'],'printing':['ap/cups'],'firmware':['a/kernel-firmware'],'calamares':[],'X11':['x/xorg-server'],'Wayland':[]}}
SAFE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9+_.:/-]{0,120}$')

BASE_STYLE='''
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; }
QMainWindow, QWidget#root { background: %(bg)s; color: %(text)s; }
QWidget { color: %(text)s; }
QFrame#card { background: %(panel)s; border: 1px solid %(border)s; border-radius: 12px; }
QLabel#heading { font-size: 23px; font-weight: 750; }
QLabel#muted { color: %(muted)s; }
QLineEdit, QComboBox, QTextEdit, QTableWidget { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 7px; padding: 7px; selection-background-color: %(select)s; selection-color: %(selecttext)s; }
QComboBox::drop-down { border: none; width: 26px; }
QPushButton { background: %(button)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: %(hover)s; }
QPushButton:disabled { color: %(muted)s; }
QPushButton#primary { background: #2563eb; color: white; border: 1px solid #2563eb; }
QPushButton#primary:hover { background: #1d4ed8; }
QTabWidget::pane { border: 1px solid %(border)s; border-radius: 10px; background: %(panel)s; top: -1px; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: %(muted)s; border: none; border-bottom: 2px solid transparent; padding: 13px 19px; margin-right: 4px; font-weight: 600; }
QTabBar::tab:hover { color: %(text)s; background: %(hover)s; }
QTabBar::tab:selected { color: %(accent)s; border-bottom: 2px solid %(accent)s; background: %(panel)s; }
QHeaderView::section { background: %(header)s; color: %(text)s; border: none; border-bottom: 1px solid %(border)s; padding: 9px; font-weight: 700; }
QTableWidget { gridline-color: %(border)s; alternate-background-color: %(alternate)s; }
QTableWidget::item:selected { background: %(select)s; color: %(selecttext)s; }
QCheckBox { spacing: 8px; }
QSplitter::handle { background: %(border)s; height: 5px; }
QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; }
QMenu::item:selected { background: %(select)s; color: %(selecttext)s; }
'''
PALETTES={'Clair':dict(bg='#f3f5f9',panel='#ffffff',text='#1c2636',muted='#637287',border='#dce3ed',button='#eef2f8',hover='#e5ecf7',header='#edf2f8',alternate='#f8fafd',select='#d9e9ff',selecttext='#122d50',accent='#2563eb'),'Sombre':dict(bg='#101721',panel='#192332',text='#eaf0fa',muted='#9bacbf',border='#344357',button='#273549',hover='#32445d',header='#253347',alternate='#1d2a3b',select='#235b96',selecttext='#ffffff',accent='#83b6ff')}

def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'UniversalLinuxBuilder/1.5','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=18) as response:return json.load(response)

def lookup(distro,query):
    if distro!='Arch Linux':
        raise RuntimeError('Recherche distante fiable non configurée pour '+distro+'. Utiliser l’ajout manuel, puis résoudre avec le gestionnaire natif.')
    data=get_json('https://archlinux.org/packages/search/json/?q='+urllib.parse.quote(query))
    return [dict(name=p['pkgname'],version=str(p.get('pkgver','')),repo=p.get('repo',''),arch=p.get('arch',''),description=p.get('pkgdesc') or '',size=p.get('compressed_size')) for p in data.get('results',[]) if p.get('arch') in ('x86_64','any')][:120]

def arch_resolve(names,limit=180):
    graph={};meta={};warnings=[];queue=[];visited=set();queued=set()
    for name in names:
        matches=[p for p in lookup('Arch Linux',name) if p['name']==name]
        if matches:queue.append(matches[0]);queued.add(name)
        else:warnings.append(name+': paquet absent ou nom virtuel')
    while queue:
        p=queue.pop(0);name=p['name'];queued.discard(name)
        if name in visited:continue
        if len(visited)>=limit:warnings.append('Limite de résolution atteinte');break
        visited.add(name);meta[name]=p
        try:
            path='/'.join(urllib.parse.quote(str(p[k]),safe='') for k in ('repo','arch','name'))
            info=get_json('https://archlinux.org/packages/'+path+'/json/')
            meta[name]['size']=info.get('compressed_size')
        except Exception as exc:
            warnings.append(name+': métadonnées indisponibles: '+str(exc));graph[name]=[];continue
        deps=[]
        for raw in info.get('depends') or []:
            dep=re.split(r'[<>=:]',str(raw),1)[0].strip()
            if not SAFE.fullmatch(dep):warnings.append(name+': dépendance illisible '+str(raw));continue
            deps.append(dep)
            if dep in visited or dep in queued:continue
            try:
                matches=[x for x in lookup('Arch Linux',dep) if x['name']==dep]
                if matches:queue.append(matches[0]);queued.add(dep)
                else:warnings.append(name+': '+dep+' introuvable ou virtuel')
            except Exception as exc:warnings.append(name+': '+dep+': '+str(exc))
        graph[name]=list(dict.fromkeys(deps))
    return graph,meta,warnings

class Worker(QThread):
    done=Signal(object,str)
    def __init__(self,mode,*args):super().__init__();self.mode=mode;self.args=args
    def run(self):
        try:
            value=lookup(*self.args) if self.mode=='search' else arch_resolve(*self.args)
            self.done.emit(value,'')
        except Exception as exc:self.done.emit(None,str(exc))

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Universal Linux Builder v1.5');self.resize(1290,870)
        self.roots={};self.app_graph={};self.app_meta={};self.app_warnings={};self.system_scan={};self.worker=None;self.context_revision=0
        root=QWidget();root.setObjectName('root');self.setCentralWidget(root);outer=QVBoxLayout(root);outer.setContentsMargins(24,18,24,22);outer.setSpacing(15)
        head=QHBoxLayout();title=QLabel('Universal Linux Builder');title.setObjectName('heading');head.addWidget(title);head.addStretch();head.addWidget(QLabel('Apparence'));self.theme=QComboBox();self.theme.addItems(['Automatique','Clair','Sombre']);self.theme.currentTextChanged.connect(self.apply_theme);head.addWidget(self.theme);outer.addLayout(head)
        subtitle=QLabel('Configuration de distribution Linux • Analyse des paquets • Préparation ISO');subtitle.setObjectName('muted');outer.addWidget(subtitle)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        self.make_distribution();self.make_system();self.make_apps();self.make_project();self.distro_changed(self.distro.currentText());self.apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(lambda *_:self.apply_theme())
    def apply_theme(self,*_):
        theme=self.theme.currentText()
        if theme=='Automatique':theme='Sombre' if QApplication.styleHints().colorScheme()==Qt.ColorScheme.Dark else 'Clair'
        self.setStyleSheet(BASE_STYLE%PALETTES[theme])
    def page(self,name):
        w=QWidget();lay=QVBoxLayout(w);lay.setContentsMargins(20,20,20,20);lay.setSpacing(14);self.tabs.addTab(w,name);return lay
    def combo(self,values):c=QComboBox();c.addItems(values);return c
    def table(self,headers):
        t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers);t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True);t.verticalHeader().setVisible(False);t.verticalHeader().setDefaultSectionSize(36);t.horizontalHeader().setStretchLastSection(True);return t
    def cell(self,t,r,c,value,data=None):
        item=QTableWidgetItem(str(value));
        if data is not None:item.setData(Qt.ItemDataRole.UserRole,data)
        t.setItem(r,c,item)
    def make_distribution(self):
        l=self.page('Distribution');form=QFormLayout();self.distro=self.combo(list(DISTROS));self.release=self.combo([]);form.addRow('Distribution',self.distro);form.addRow('Version',self.release);l.addLayout(form);info=QLabel('Les profils dépendent de la famille et de la version sélectionnées.');info.setObjectName('muted');l.addWidget(info);l.addStretch();self.distro.currentTextChanged.connect(self.distro_changed);self.release.currentTextChanged.connect(self.release_changed)
    def make_system(self):
        l=self.page('Système');form=QFormLayout();self.desktop=self.combo(DESKTOPS);self.display=self.combo(['Aucun','X11','Wayland']);self.audio=self.combo(['Aucun','PipeWire','PulseAudio','ALSA']);self.kernel=self.combo(['Stable','LTS','Hardened'])
        for name,widget in [('Bureau',self.desktop),('Affichage',self.display),('Audio',self.audio),('Noyau Linux',self.kernel)]:form.addRow(name,widget)
        l.addLayout(form);self.options={}
        for key,label,default in [('wifi','Wi-Fi',True),('bluetooth','Bluetooth',True),('printing','Imprimantes / CUPS',False),('firmware','Firmwares',True),('calamares','Préparer Calamares',True)]:
            cb=QCheckBox(label);cb.setChecked(default);self.options[key]=cb;l.addWidget(cb);cb.toggled.connect(self.system_changed)
        self.kernel_note=QLabel();self.kernel_note.setWordWrap(True);l.addWidget(self.kernel_note)
        self.system_status=QLabel('Analyse non lancée.');self.system_status.setWordWrap(True);l.addWidget(self.system_status)
        self.scan_button=QPushButton('Analyser les dépendances du système');self.scan_button.setObjectName('primary');self.scan_button.clicked.connect(self.scan_system);l.addWidget(self.scan_button)
        l.addStretch();self.desktop.currentTextChanged.connect(self.desktop_changed);self.display.currentTextChanged.connect(self.system_changed);self.audio.currentTextChanged.connect(self.system_changed);self.kernel.currentTextChanged.connect(self.system_changed)
    def distro_changed(self,distro):
        self.context_revision+=1;self.release.blockSignals(True);self.release.clear();self.release.addItems(DISTROS[distro]);self.release.blockSignals(False)
        old=self.desktop.currentText();allowed=['Aucun']+list(PROFILES[distro]);self.desktop.blockSignals(True);self.desktop.clear();self.desktop.addItems(allowed);self.desktop.setCurrentText(old if old in allowed else 'Aucun');self.desktop.blockSignals(False)
        if hasattr(self,'repo_distro'):
            self.repo_distro.blockSignals(True);self.repo_distro.setCurrentText(distro);self.repo_distro.blockSignals(False);self.repo_release.blockSignals(True);self.repo_release.clear();self.repo_release.addItems(DISTROS[distro]);self.repo_release.setCurrentText(self.release.currentText());self.repo_release.blockSignals(False)
        self.clear_apps();self.desktop_changed(self.desktop.currentText());self.system_changed()
    def release_changed(self,version):
        self.context_revision+=1
        if hasattr(self,'repo_release'):self.repo_release.setCurrentText(version)
        self.clear_apps();self.system_changed()
    def desktop_changed(self,desktop):
        profile=PROFILES[self.distro.currentText()].get(desktop)
        self.display.blockSignals(True);self.display.setCurrentText(profile[2] if profile else 'Aucun');self.display.blockSignals(False);self.system_changed()
    def system_changed(self,*_):
        self.context_revision+=1;self.system_scan={}
        if not hasattr(self,'system_status'):return
        distro=self.distro.currentText();kernel=self.kernel.currentText();mapped=KERNELS[distro].get(kernel)
        self.kernel_note.setText('Noyau : '+(', '.join(mapped) if mapped else kernel+' — variante non définie pour cette distribution'))
        self.system_status.setText('Configuration modifiée : relancer « Analyser les dépendances du système ».')
    def make_apps(self):
        l=self.page('Applications');form=QFormLayout();self.repo_distro=self.combo(list(DISTROS));self.repo_release=self.combo([]);form.addRow('Catalogue',self.repo_distro);form.addRow('Branche',self.repo_release);l.addLayout(form)
        self.repo_distro.currentTextChanged.connect(self.repo_changed)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('Rechercher un paquet (Arch) ou ajouter manuellement');self.query.returnPressed.connect(self.start_search);self.search_button=QPushButton('Rechercher');self.search_button.setObjectName('primary');self.search_button.clicked.connect(self.start_search);bar.addWidget(self.query);bar.addWidget(self.search_button);l.addLayout(bar)
        split=QSplitter(Qt.Orientation.Vertical);self.results=self.table(['Application','Version','Dépôt','Description']);self.results.setColumnWidth(0,260);self.results.setColumnWidth(1,155);self.results.setColumnWidth(2,140);self.results.setSortingEnabled(True);self.results.cellDoubleClicked.connect(self.add_result);split.addWidget(self.results)
        self.selected=self.table(['Paquet','Rôle','Version','Taille']);self.selected.setColumnWidth(0,320);self.selected.setColumnWidth(1,190);self.selected.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.selected.customContextMenuRequested.connect(self.remove_menu);split.addWidget(self.selected);split.setSizes([380,250]);l.addWidget(split,1)
        bar2=QHBoxLayout();self.manual=QLineEdit();self.manual.setPlaceholderText('Nom exact du paquet (ajout non vérifié)');b=QPushButton('Ajouter manuellement');b.clicked.connect(self.add_manual);bar2.addWidget(self.manual);bar2.addWidget(b);l.addLayout(bar2);self.app_status=QLabel('Arch : catalogue officiel. Autres familles : ajout manuel en attente de solveur natif.');self.app_status.setWordWrap(True);l.addWidget(self.app_status)
        self.repo_changed(self.repo_distro.currentText())
    def repo_changed(self,distro):
        self.repo_release.blockSignals(True);self.repo_release.clear();self.repo_release.addItems(DISTROS[distro]);self.repo_release.blockSignals(False);self.clear_apps()
    def clear_apps(self):
        self.roots.clear();self.app_graph.clear();self.app_meta.clear();self.app_warnings.clear()
        if hasattr(self,'results'):self.results.setRowCount(0)
        if hasattr(self,'selected'):self.selected.setRowCount(0)
    def matching(self):return self.repo_distro.currentText()==self.distro.currentText() and self.repo_release.currentText()==self.release.currentText()
    def start_worker(self,mode,args,callback):
        if self.worker is not None:
            QMessageBox.information(self,'Opération en cours','Veuillez attendre la fin de l’analyse actuelle.');return False
        worker=Worker(mode,*args);self.worker=worker;self.search_button.setEnabled(False);self.scan_button.setEnabled(False)
        worker.done.connect(callback);worker.finished.connect(lambda:self.worker_finished(worker));worker.start();return True
    def worker_finished(self,worker):
        if self.worker is worker:self.worker=None
        self.search_button.setEnabled(True);self.scan_button.setEnabled(True);worker.deleteLater()
    def start_search(self):
        q=self.query.text().strip()
        if not q or len(q)>80:QMessageBox.warning(self,'Recherche','Saisir 1 à 80 caractères.');return
        if not self.matching():QMessageBox.warning(self,'Catalogue','La branche doit correspondre au projet.');return
        if self.distro.currentText()!='Arch Linux':
            self.app_status.setText('Recherche distante non disponible pour '+self.distro.currentText()+'. Ajout manuel possible.');return
        context=self.context_revision;self.results.setRowCount(0);self.app_status.setText('Recherche en cours...')
        self.start_worker('search',(self.distro.currentText(),q),lambda result,error:self.search_done(result,error,context))
    def search_done(self,rows,error,context):
        if context!=self.context_revision:return
        if error:self.app_status.setText('Erreur : '+error);return
        self.results.setSortingEnabled(False)
        for p in rows:
            r=self.results.rowCount();self.results.insertRow(r)
            for c,v in enumerate([p['name'],p['version'],p['repo'],p['description']]):self.cell(self.results,r,c,v,p if c==0 else None)
        self.results.setSortingEnabled(True);self.app_status.setText(str(len(rows))+' résultats — double-clic pour ajouter.')
    def add_result(self,row,_col):
        if not self.matching():return
        item=self.results.item(row,0)
        if not item:return
        p=item.data(Qt.ItemDataRole.UserRole)
        if not p or p['name'] in self.roots:return
        context=self.context_revision;self.app_status.setText('Analyse des dépendances de '+p['name']+'...')
        self.start_worker('resolve',([p['name']],),lambda result,error:self.app_done(result,error,p,context))
    def app_done(self,result,error,p,context):
        if context!=self.context_revision:return
        if error:self.app_status.setText('Erreur : '+error);return
        graph,meta,warnings=result;self.roots[p['name']]=p;self.app_graph.update(graph);self.app_meta.update(meta)
        if warnings:self.app_warnings[p['name']]=warnings
        self.refresh();self.app_status.setText(p['name']+' ajouté · '+str(len(graph))+' paquets analysés · '+str(len(warnings))+' avertissements.')
    def add_manual(self):
        name=self.manual.text().strip()
        if not SAFE.fullmatch(name):QMessageBox.warning(self,'Paquet','Nom invalide.');return
        if name not in self.roots:
            p={'name':name,'version':'?','repo':'manuel','size':None};self.roots[name]=p;self.app_meta[name]=p;self.app_warnings[name]=['Dépendances non vérifiées'];self.refresh()
        self.manual.clear()
    def needed_apps(self):
        needed=set();stack=list(self.roots)
        while stack:
            name=stack.pop()
            if name in needed:continue
            needed.add(name);stack.extend(self.app_graph.get(name,[]))
        return needed
    def refresh(self):
        self.selected.setRowCount(0)
        for name in sorted(self.needed_apps()):
            p=self.app_meta.get(name,{});r=self.selected.rowCount();self.selected.insertRow(r);role='Application' if name in self.roots else 'Dépendance'
            if name in self.app_warnings:role+=' ⚠'
            for c,v in enumerate([name,role,p.get('version','?'),self.human(p.get('size'))]):self.cell(self.selected,r,c,v,name if c==0 else None)
    def remove_menu(self,point):
        item=self.selected.itemAt(point)
        if not item:return
        name=self.selected.item(item.row(),0).data(Qt.ItemDataRole.UserRole)
        if name not in self.roots:return
        menu=QMenu(self);action=menu.addAction('Retirer l’application et les dépendances orphelines')
        if menu.exec(self.selected.viewport().mapToGlobal(point))!=action:return
        before=self.needed_apps();self.roots.pop(name,None);self.app_warnings.pop(name,None);after=self.needed_apps();self.refresh();self.app_status.setText(name+' retiré · '+str(max(0,len(before-after)-1))+' dépendances orphelines retirées.')
    def system_seeds(self):
        distro=self.distro.currentText();desktop=self.desktop.currentText();kernel=self.kernel.currentText();display=self.display.currentText();audio=self.audio.currentText();profile=PROFILES[distro].get(desktop);extras=EXTRA[distro];categories={}
        categories['Base']=list(extras['base']);categories['Noyau']=list(KERNELS[distro].get(kernel,[]));categories['Bureau']=list(profile[0]) if profile else [];categories['Affichage']=list(extras.get(display,[])) if desktop!='Aucun' else [];categories['Audio']=list(AUDIO[distro].get(audio,[]))
        for key,label in [('wifi','Wi-Fi'),('bluetooth','Bluetooth'),('printing','Impression'),('firmware','Firmwares'),('calamares','Installateur')]:categories[label]=list(extras.get(key,[])) if self.options[key].isChecked() else []
        return categories
    def scan_system(self):
        distro=self.distro.currentText();seeds=self.system_seeds();names=sorted({name for values in seeds.values() for name in values});context=self.context_revision
        if distro!='Arch Linux':
            self.system_scan={'distro':distro,'seeds':names,'graph':{},'meta':{},'warnings':['Résolution transitive non disponible pour '+distro+'. Exécuter le solveur natif dans un environnement compatible.'],'verified':False}
            self.system_status.setText(distro+' : '+str(len(names))+' paquets de départ identifiés. Dépendances transitives NON résolues.');return
        self.system_status.setText('Arch : résolution récursive du système en cours (réseau nécessaire)...')
        self.start_worker('resolve',(names,),lambda result,error:self.system_done(result,error,context,names))
    def system_done(self,result,error,context,names):
        if context!=self.context_revision:return
        if error:self.system_scan={};self.system_status.setText('Erreur : '+error);return
        graph,meta,warnings=result;self.system_scan={'distro':'Arch Linux','seeds':names,'graph':graph,'meta':meta,'warnings':warnings,'verified':not warnings}
        self.system_status.setText('Arch : '+str(len(graph))+' paquets examinés ; '+str(len(warnings))+' avertissements. Solveur pacman toujours nécessaire.')
    def all_packages(self):
        packages={name for values in self.system_seeds().values() for name in values};packages.update(self.needed_apps())
        if self.system_scan:
            packages.update(self.system_scan.get('graph',{}))
            for deps in self.system_scan.get('graph',{}).values():packages.update(deps)
        return sorted(packages)
    def human(self,size):return f'{size/1048576:.1f} Mio' if isinstance(size,(int,float)) and size>=0 else 'Inconnue'
    def make_project(self):
        l=self.page('Projet / ISO');self.summary=QLabel('Cliquez sur Vérifier pour voir les paquets et l’estimation indicative.');self.summary.setWordWrap(True);l.addWidget(self.summary)
        self.preview=self.table(['Paquet','Catégorie','Version','Taille compressée']);self.preview.setColumnWidth(0,340);self.preview.setColumnWidth(1,180);self.preview.setColumnWidth(2,160);l.addWidget(self.preview,2)
        self.report=QTextEdit();self.report.setReadOnly(True);l.addWidget(self.report,1)
        row=QHBoxLayout();b=QPushButton('Vérifier');b.clicked.connect(self.check);e=QPushButton('Exporter le projet');e.setObjectName('primary');e.clicked.connect(self.export);row.addWidget(b);row.addWidget(e);l.addLayout(row)
    def check(self):
        distro=self.distro.currentText();desktop=self.desktop.currentText();kernel=self.kernel.currentText();profile=PROFILES[distro].get(desktop);categories=self.system_seeds();all_names=self.all_packages();errors=[];warnings=[]
        if kernel not in KERNELS[distro]:errors.append('Noyau '+kernel+' indisponible dans le profil '+distro+'.')
        if desktop=='Aucun' and self.display.currentText()!='Aucun':errors.append('Sans bureau, affichage doit être Aucun.')
        if desktop!='Aucun' and self.display.currentText()=='Aucun':errors.append('Un bureau exige un affichage.')
        if self.app_warnings:warnings.append(str(len(self.app_warnings))+' applications avec dépendances non résolues.')
        if not self.system_scan:warnings.append('Analyse des dépendances système non lancée.')
        else:warnings.extend(self.system_scan.get('warnings',[]))
        if self.system_scan and not self.system_scan.get('verified'):warnings.append('Le système n’est pas intégralement résolu.')
        warnings.append('Les fournisseurs virtuels, conflits et tailles doivent être validés par le solveur natif avant ISO.')
        meta=dict(self.system_scan.get('meta',{})) if self.system_scan else {};meta.update(self.app_meta);self.preview.setRowCount(0);known=0;unknown=0
        for name in all_names:
            p=meta.get(name,{});size=p.get('size');r=self.preview.rowCount();self.preview.insertRow(r)
            role=next((cat for cat,values in categories.items() if name in values),'Application' if name in self.roots else 'Dépendance')
            for c,v in enumerate([name,role,p.get('version','?'),self.human(size)]):self.cell(self.preview,r,c,v)
            if isinstance(size,(int,float)) and size>=0:known+=size
            else:unknown+=1
        low=known/1048576+unknown*2+180;high=known/1048576+unknown*35+700
        self.summary.setText(f'{len(all_names)} paquets connus · {len(self.roots)} applications · {unknown} tailles inconnues\nFourchette indicative non validée : {low/1024:.2f} à {high/1024:.2f} Gio. Aucune ISO créée.')
        self.report.setPlainText('ERREURS\n'+('\n'.join(errors) or 'Aucune erreur de formulaire')+'\n\nAVERTISSEMENTS\n'+'\n'.join(warnings))
        cfg={'schema':15,'app_version':VERSION,'distribution':distro,'version':self.release.currentText(),'desktop':desktop,'display':self.display.currentText(),'audio':self.audio.currentText(),'kernel':kernel,'kernel_packages':KERNELS[distro].get(kernel,[]),'display_manager':profile[1] if profile else None,'system_categories':categories,'applications':sorted(self.roots),'application_graph':self.app_graph,'system_scan':self.system_scan,'all_packages':all_names,'warnings':warnings,'errors':errors,'iso_size_estimate':{'known_compressed_bytes':known,'unknown_packages':unknown,'low_mib':round(low,1),'high_mib':round(high,1)}}
        return cfg,errors
    def export(self):
        cfg,errors=self.check()
        if errors:QMessageBox.warning(self,'Export','Corrigez les erreurs avant export.');return
        directory=QFileDialog.getExistingDirectory(self,'Dossier de projet vide',str(Path.home()))
        if not directory:return
        path=Path(directory)
        if any(path.iterdir()):QMessageBox.warning(self,'Export','Choisissez un dossier vide.');return
        (path/'project_v1_5.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        (path/'packages_v1_5.txt').write_text('\n'.join(cfg['all_packages'])+'\n',encoding='utf-8')
        (path/'README_v1_5.txt').write_text('Projet préparatoire uniquement. Aucun ISO généré.\nLes dépendances doivent être validées par le solveur natif.\n',encoding='utf-8')
        QMessageBox.information(self,'Export','Configuration et liste des paquets exportées. Aucune ISO créée.')

if __name__=='__main__':
    app=QApplication(sys.argv);app.setStyle('Fusion');w=Window();w.show();sys.exit(app.exec())
