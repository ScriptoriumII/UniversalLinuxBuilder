import sys,re,shlex,json,subprocess,datetime
from pathlib import Path
from PySide6.QtCore import Qt,QThread,Signal
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QComboBox,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QLabel,QCheckBox,QTextEdit,QFileDialog,QMessageBox,QInputDialog,QGroupBox,QSplitter,QHeaderView)

VERSION='1.13'
FAMILIES=['Debian','Fedora','Arch Linux','Gentoo','Slackware']
RELEASES={'Debian':['trixie','bookworm'],'Fedora':['44','43','42'],'Arch Linux':['rolling'],'Gentoo':['stable','testing'],'Slackware':['15.0','current']}
BASE={'Debian':['live-boot','live-config','linux-image-amd64','network-manager'],'Fedora':['kernel','NetworkManager'],'Arch Linux':['base','linux','networkmanager'],'Gentoo':['sys-kernel/gentoo-kernel','net-misc/networkmanager'],'Slackware':['kernel-generic','networkmanager']}
DESKTOP={'Debian':{'GNOME':['gnome-core','gdm3'],'KDE Plasma':['kde-plasma-desktop','sddm'],'Xfce':['xfce4','lightdm']},'Fedora':{'GNOME':['gnome-shell','gdm'],'KDE Plasma':['plasma-desktop','sddm'],'Xfce':['xfce4-session','xfce4-panel']},'Arch Linux':{'GNOME':['gnome','gdm'],'KDE Plasma':['plasma','sddm'],'Xfce':['xfce4','lightdm']},'Gentoo':{'GNOME':['gnome-base/gnome'],'KDE Plasma':['kde-plasma/plasma-meta'],'Xfce':['xfce-base/xfce4-meta']},'Slackware':{'KDE Plasma':['plasma-desktop'],'Xfce':['xfce4-session']}}
AUDIO={'Debian':{'PipeWire':['pipewire','wireplumber','pipewire-pulse'],'PulseAudio':['pulseaudio']},'Fedora':{'PipeWire':['pipewire','wireplumber','pipewire-pulseaudio'],'PulseAudio':['pulseaudio']},'Arch Linux':{'PipeWire':['pipewire','wireplumber','pipewire-pulse'],'PulseAudio':['pulseaudio']},'Gentoo':{'PipeWire':['media-video/pipewire'],'PulseAudio':['media-sound/pulseaudio']},'Slackware':{'PipeWire':['pipewire'],'PulseAudio':['pulseaudio']}}
TOOLS={'Debian':[('lb','live-build'),('debootstrap','debootstrap'),('mksquashfs','squashfs-tools'),('xorriso','xorriso'),('grub-mkrescue','grub-common')],'Fedora':[('dnf5','dnf5'),('livemedia-creator','lorax'),('xorriso','xorriso'),('mksquashfs','squashfs-tools')],'Arch Linux':[('mkarchiso','archiso'),('pacman','pacman'),('mksquashfs','squashfs-tools'),('xorriso','libisoburn')],'Gentoo':[('emerge','sys-apps/portage'),('mksquashfs','sys-fs/squashfs-tools'),('xorriso','app-cdr/libisoburn')],'Slackware':[('slackpkg','slackpkg'),('mkisofs','cdrtools'),('mksquashfs','squashfs-tools')]}
SAFE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$')
ANSI=re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|\([^\x1b])')
def clean(s): return ANSI.sub('',s).replace('\r','\n').replace('\x08','')
def decode(b):
    if b.startswith((b'\xff\xfe',b'\xfe\xff')): return clean(b.decode('utf-16','replace'))
    if b'\x00' in b[:80]: return clean(b.decode('utf-16-le','replace').lstrip('\ufeff'))
    return clean(b.decode('utf-8','replace'))
def run(argv,timeout=300):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return decode(p.stdout),decode(p.stderr),p.returncode
def wsl(env,script,timeout=300,root=False):
    a=['wsl.exe','-d',env]
    if root:a+=['-u','root']
    return run(a+['--exec','/bin/sh','-lc',script],timeout)
def installed():
    out,err,rc=run(['wsl.exe','--list','--quiet'],60)
    if rc:raise RuntimeError(err or out)
    return [s.strip().lstrip('\ufeff') for s in out.splitlines() if s.strip()]
def catalog():
    out,err,rc=run(['wsl.exe','--list','--online'],90)
    if rc:raise RuntimeError(err or out)
    rows=[]
    for line in out.splitlines():
        m=re.match(r'^\s*([A-Za-z0-9][\w.-]*)\s{2,}(.+?)\s*$',line)
        if m and m.group(1).lower() not in ('name','nom'):rows.append((m.group(1),m.group(2)))
    return rows,out

def detect(env):
    out,err,rc=wsl(env,'cat /etc/os-release',60)
    if rc:raise RuntimeError(err or out)
    d={}
    for line in out.splitlines():
        if '=' in line:
            k,v=line.split('=',1);d[k]=v.strip().strip('"')
    ident=d.get('ID','').lower();like=d.get('ID_LIKE','').lower().split()
    if ident=='debian':family='Debian'
    elif ident=='fedora':family='Fedora'
    elif ident in ('arch','archlinux'):family='Arch Linux'
    elif ident=='gentoo':family='Gentoo'
    elif ident=='slackware':family='Slackware'
    else:family='Non prise en charge ('+ident+')'
    return family,d

def prereq(env):
    family,meta=detect(env)
    if family not in TOOLS:return family,meta,[], 'Distribution non prise en charge.'
    names=[x[0] for x in TOOLS[family]]
    cmd='; '.join('if command -v '+shlex.quote(n)+' >/dev/null 2>&1; then echo '+shlex.quote(n+':OK')+'; else echo '+shlex.quote(n+':MISSING')+'; fi' for n in names)
    out,err,rc=wsl(env,cmd,90)
    if rc:raise RuntimeError(err or out)
    flags={}
    for line in out.splitlines():
        if ':' in line:
            k,v=line.split(':',1);flags[k]=v=='OK'
    rows=[(name,package,'Présent' if flags.get(name) else 'Absent') for name,package in TOOLS[family]]
    extra=''
    if family=='Arch Linux':
        o,e,c=wsl(env,'test -f /usr/share/archiso/configs/releng/profiledef.sh',60)
        extra='Profil releng : '+('présent' if c==0 else 'absent')
    return family,meta,rows,extra

def install_prereqs(env):
    family,meta,rows,extra=prereq(env)
    if family not in TOOLS:raise RuntimeError('Famille non prise en charge')
    missing=sorted(set(pkg for _,pkg,status in rows if status=='Absent'))
    if not missing:return family,'Aucun prérequis manquant.',('', '',0)
    if family=='Debian':cmd='DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends '+' '.join(map(shlex.quote,missing))
    elif family=='Fedora':cmd='dnf5 -y install '+' '.join(map(shlex.quote,missing))
    elif family=='Arch Linux':cmd='pacman --noconfirm -Syu --needed '+' '.join(map(shlex.quote,missing))
    else:raise RuntimeError('Installation automatique non proposée pour '+family+' : configurer manuellement le système et les dépôts.')
    result=wsl(env,cmd,3600,True)
    return family,cmd,result

def update_repos(env):
    family,_=detect(env)
    commands={'Debian':'DEBIAN_FRONTEND=noninteractive apt-get update','Fedora':'dnf5 makecache --refresh','Arch Linux':'pacman -Syu --noconfirm','Gentoo':'emerge --sync','Slackware':'slackpkg update'}
    if family not in commands:raise RuntimeError('Famille non prise en charge')
    return family,commands[family],wsl(env,commands[family],3600,True)

def search(env,family,q):
    cmds={'Debian':'apt-cache search','Fedora':'dnf5 search','Arch Linux':'pacman -Ss','Gentoo':'emerge --search','Slackware':'slackpkg search'}
    return wsl(env,'LC_ALL=C '+cmds[family]+' '+shlex.quote(q),240)

def parse_search(family,out):
    rows=[];seen=set()
    for s in out.splitlines():
        s=s.strip();name='';version='?';desc=''
        if family=='Debian':
            m=re.match(r'^([\w+.-]+)\s+-\s+(.+)$',s)
            if m:name,desc=m.groups()
        elif family=='Fedora':
            m=re.match(r'^([\w+.-]+)\.(?:x86_64|noarch|aarch64|i686|src)\s*(?::|\s)\s*(.*)$',s)
            if m:name,desc=m.groups()
        elif family=='Arch Linux':
            m=re.match(r'^[\w+.-]+/([^ ]+)\s+([^ ]+)',s)
            if m:name,version=m.groups()
        elif family=='Gentoo':
            m=re.search(r'\*\s+([\w+.-]+/[\w+.-]+)',s)
            if m:name=m.group(1)
        else:
            m=re.search(r'([\w+.-]+)-([0-9][\w.+-]*)-(?:x86_64|noarch|i[3-6]86)',s)
            if m:name,version=m.groups()
        if name and SAFE.fullmatch(name) and name not in seen:seen.add(name);rows.append((name,version,desc[:150]))
    return rows[:600]

def simulate(env,family,packages):
    args=' '.join(map(shlex.quote,packages))
    commands={'Debian':'LC_ALL=C apt-get -s install '+args,'Fedora':'LC_ALL=C dnf5 --assumeno install '+args,'Arch Linux':'LC_ALL=C pacman -Sp --print-format "%n|%v|%s" '+args,'Gentoo':'LC_ALL=C emerge --pretend --verbose --tree '+args,'Slackware':'echo "Slackware : pas de solveur natif de dépendances"'}
    return wsl(env,commands[family],600)

def parse_size(s):
    m=re.search(r'([\d.,]+)\s*(B|KiB|MiB|GiB)',s,re.I)
    if not m:return None
    try:return int(float(m.group(1).replace(',','.'))*{'b':1,'kib':1024,'mib':1024**2,'gib':1024**3}[m.group(2).lower()])
    except ValueError:return None
def human(n):
    if n is None:return '—'
    for unit in ('o','Kio','Mio','Gio','Tio'):
        if n<1024:return f'{n:.1f} {unit}'
        n/=1024
    return f'{n:.1f} Pio'
def parse_transaction(family,out,requested):
    rows={p:{'version':'?','size':None,'status':'Demandé'} for p in requested}
    for s in out.splitlines():
        if family=='Debian':
            m=re.match(r'^Inst\s+(\S+)(?:\s+\[.*?\])?\s+\(([^ )]+)',s)
            if m:rows[m.group(1)]={'version':m.group(2),'size':None,'status':'Transaction'}
        elif family=='Arch Linux':
            m=re.match(r'^([^|]+)\|([^|]+)\|(\d+)$',s.strip())
            if m:rows[m.group(1)]={'version':m.group(2),'size':int(m.group(3)),'status':'Téléchargement'}
        elif family=='Fedora':
            m=re.match(r'^\s*([\w+.-]+)\s+(?:x86_64|noarch|aarch64|i686)\s+(\S+)\s+(\S+)(?:\s+(.+))?$',s)
            if m and m.group(3).lower() not in ('arch','version'):
                rows[m.group(1)]={'version':m.group(2),'size':parse_size(m.group(4) or ''),'status':'Transaction'}
        elif family=='Gentoo':
            m=re.search(r'\[ebuild[^]]*\]\s+([\w+.-]+/[\w+.-]+)-([\w.+-]+)',s)
            if m:rows[m.group(1)]={'version':m.group(2),'size':None,'status':'Transaction'}
    return rows

def assessment(family,out,err,rc):
    if rc==0:return True,'Simulation terminée'
    if family=='Fedora':
        text=out+'\n'+err
        if re.search(r'(?m)^\s*Package\s+Arch\s+Version',text) and re.search(r'Transaction Summary|Total download size',text,re.I) and re.search(r'Operation aborted|Operation cancelled|Operation canceled|Is this ok',text,re.I):return True,'Aperçu DNF5 obtenu (refus --assumeno)'
    return False,'Erreur de simulation (code '+str(rc)+')'

def estimate(rows):
    values=[v['size'] for v in rows.values() if v.get('size') is not None]
    if not values:return 'Indisponible : pas de données de taille'
    coverage=len(values)/max(1,len(rows))
    if coverage<0.35:return f'Insuffisant : {human(sum(values))} mesurés sur {len(values)}/{len(rows)} paquets'
    basis=sum(values)/coverage
    return f'{human(int(basis*.8+650*1024**2))} à {human(int(basis*2+1700*1024**2))} (très approximatif)'

def build(env,family,release,packages,target):
    if family not in ('Debian','Arch Linux'):raise RuntimeError('Chaîne ISO non intégrée pour '+family)
    actual,meta,checks,extra=prereq(env)
    if actual!=family:raise RuntimeError('Famille WSL incorrecte : '+actual)
    missing=[p for tool,p,status in checks if status=='Absent']
    if missing:raise RuntimeError('Prérequis absents : '+', '.join(missing)+' ; utiliser WSL2 > Installer les prérequis.')
    if family=='Arch Linux' and 'absent' in extra:raise RuntimeError('Profil releng absent ; réinstaller archiso.')
    folder=Path(target)
    if any(folder.iterdir()):raise RuntimeError('Choisir un dossier de destination vide.')
    # Travail dans le filesystem Linux (évite /mnt/c pour les permissions/montages).
    workspace='/var/tmp/ulb-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    qwork=shlex.quote(workspace)
    p_args=' '.join(shlex.quote(p) for p in packages)
    if family=='Debian':
        script=('set -eu; mkdir -p '+qwork+'; cd '+qwork+'; '
                'lb config --distribution '+shlex.quote(release)+' --architectures amd64 --binary-images iso-hybrid; '
                'mkdir -p config/package-lists; printf "%s\\n" '+p_args+' > config/package-lists/ulb.list.chroot; '
                'lb build')
    else:
        script=('set -eu; mkdir -p '+qwork+'; cp -a /usr/share/archiso/configs/releng '+qwork+'/profile; '
                'cd '+qwork+'; printf "%s\\n" '+p_args+' >> profile/packages.x86_64; '
                'sort -u profile/packages.x86_64 -o profile/packages.x86_64; '
                'mkdir -p out work; mkarchiso -v -w work -o out profile')
    out,err,rc=wsl(env,script,7200,True)
    report=f'Famille: {family}\nWSL: {env}\nWorkspace Linux: {workspace}\nCode: {rc}\n\n{out}\n{err}'
    (folder/'build_report.txt').write_text(report,encoding='utf-8')
    if rc:raise RuntimeError(f'Construction échouée (code {rc}). Journal : {folder / "build_report.txt"}\n'+(err or out)[-2200:])
    find='find '+qwork+' -type f -name "*.iso" -print'
    paths,e,c=wsl(env,find,90,True)
    if c or not paths.strip():raise RuntimeError('Aucune ISO générée. Voir build_report.txt')
    copied=[]
    for index,src in enumerate(paths.splitlines(),1):
        dest=folder/('ULB_'+family.replace(' ','_')+'_'+str(index)+'.iso')
        # Copie via stdout binaire (pas de décodage) pour conserver l'intégrité.
        with dest.open('wb') as f:
            p=subprocess.run(['wsl.exe','-d',env,'-u','root','--exec','cat',src],stdout=f,stderr=subprocess.PIPE,timeout=1800,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if p.returncode:raise RuntimeError('Copie ISO échouée : '+decode(p.stderr))
        with dest.open('rb') as f:f.seek(32768);sig=f.read(7)
        copied.append({'path':str(dest),'size':dest.stat().st_size,'iso9660':len(sig)>=6 and sig[1:6]==b'CD001','boot_tested':False,'ventoy_tested':False})
    return copied,report

class Worker(QThread):
    done=Signal(object,str)
    def __init__(self,action,*args):super().__init__();self.action=action;self.args=args
    def run(self):
        try:
            a=self.action;x=self.args
            if a=='installed':r=installed()
            elif a=='catalog':r=catalog()
            elif a=='detect':r=detect(x[0])
            elif a=='prereq':r=prereq(x[0])
            elif a=='install_prereq':r=install_prereqs(x[0])
            elif a=='update':r=update_repos(x[0])
            elif a=='install_wsl':r=run(['wsl.exe','--install','--distribution',x[0],'--no-launch'],1800)
            elif a=='delete_wsl':r=run(['wsl.exe','--unregister',x[0]],900)
            elif a=='search':r=search(*x)
            elif a=='simulate':r=simulate(*x)
            elif a=='build':r=build(*x)
            else:raise RuntimeError('Action inconnue')
            self.done.emit(r,'')
        except Exception as e:self.done.emit(None,str(e))

DARK='''QWidget{background:#151e2c;color:#ecf3ff;font:13px "Segoe UI"} QLineEdit,QComboBox,QTextEdit,QTableWidget{background:#202e42;border:1px solid #465d78;border-radius:5px;padding:5px} QPushButton{background:#304d70;border:1px solid #5b7898;border-radius:5px;padding:8px} QPushButton:hover{background:#416991} QTabBar::tab{padding:10px 15px} QTabBar::tab:selected{border-bottom:3px solid #6cb0ff} QTableWidget{alternate-background-color:#293b53;gridline-color:transparent} QHeaderView::section{background:#37516f;padding:7px;border-right:1px solid #536a83} QGroupBox{border:1px solid #455a74;margin-top:10px;padding-top:9px} QGroupBox::title{subcontrol-origin:margin;left:10px}'''
LIGHT='''QWidget{background:#f5f7fa;color:#172438;font:13px "Segoe UI"} QLineEdit,QComboBox,QTextEdit,QTableWidget{background:white;border:1px solid #bfccdc;border-radius:5px;padding:5px} QPushButton{background:#e0eaf6;border:1px solid #aebed1;border-radius:5px;padding:8px} QPushButton:hover{background:#c7dcf4} QTabBar::tab{padding:10px 15px} QTabBar::tab:selected{border-bottom:3px solid #2979dc} QTableWidget{alternate-background-color:#edf3fa;gridline-color:transparent} QHeaderView::section{background:#d9e6f3;padding:7px;border-right:1px solid #b8c8d9} QGroupBox{border:1px solid #bfccdc;margin-top:10px;padding-top:9px} QGroupBox::title{subcontrol-origin:margin;left:10px}'''

class App(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Universal Linux Builder v'+VERSION);self.resize(1400,920)
        self.inst=[];self.catalog=[];self.mapping={f:'' for f in FAMILIES};self.apps=set();self.solution={};self.valid=False;self.revision=0;self.worker=None
        center=QWidget();self.setCentralWidget(center);main=QVBoxLayout(center)
        top=QHBoxLayout();title=QLabel('Universal Linux Builder  |  v'+VERSION);title.setStyleSheet('font-size:21px;font-weight:bold');top.addWidget(title);top.addStretch();top.addWidget(QLabel('Thème'))
        self.theme=QComboBox();self.theme.addItems(['Sombre','Clair']);self.theme.currentTextChanged.connect(self.style);top.addWidget(self.theme);main.addLayout(top)
        self.tabs=QTabWidget();self.tabs.setUsesScrollButtons(True);main.addWidget(self.tabs)
        self.tab_distribution();self.tab_system();self.tab_apps();self.tab_project();self.tab_wsl()
        self.status=QLabel('Prêt');main.addWidget(self.status);self.style();self.change_family()
    def style(self,*_):self.setStyleSheet(DARK if self.theme.currentText()=='Sombre' else LIGHT)
    def page(self,name):w=QWidget();l=QVBoxLayout(w);l.setContentsMargins(14,14,14,14);self.tabs.addTab(w,name);return l
    def combo(self,items=()):c=QComboBox();c.addItems(items);return c
    def button(self,label,fn):b=QPushButton(label);b.clicked.connect(fn);return b
    def table(self,headers):
        t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers);t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True);t.setShowGrid(False);t.setWordWrap(False);t.verticalHeader().hide();t.verticalHeader().setDefaultSectionSize(30);t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive);t.horizontalHeader().setStretchLastSection(True);return t
    def fill(self,t,rows):
        t.setSortingEnabled(False);t.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate(row):t.setItem(i,j,QTableWidgetItem(str(value)))
        t.setSortingEnabled(True)
    def selected(self,t):
        row=t.currentRow();item=t.item(row,0) if row>=0 else None;return item.text() if item else ''
    def warn(self,s):QMessageBox.warning(self,'Universal Linux Builder',s)
    def info(self,s):QMessageBox.information(self,'Universal Linux Builder',s)
    def ask(self,s):return QMessageBox.question(self,'Confirmation',s)==QMessageBox.StandardButton.Yes
    def job(self,action,args,callback):
        if self.worker is not None:self.warn('Une opération est déjà en cours.');return
        w=Worker(action,*args);self.worker=w;self.status.setText('En cours : '+action);w.done.connect(callback);w.finished.connect(lambda w=w:self.finished(w));w.start()
    def finished(self,w):
        if self.worker is w:self.worker=None
        w.deleteLater();self.status.setText('Prêt')
    def invalidate(self,*_):self.revision+=1;self.valid=False
    def family(self):return self.family_box.currentText()
    def project_env(self):return self.mapping.get(self.family(),'')
    def tab_distribution(self):
        l=self.page('Distribution');f=QFormLayout();self.family_box=self.combo(FAMILIES);self.release=self.combo();f.addRow('Famille Linux',self.family_box);f.addRow('Version cible',self.release);l.addLayout(f);label=QLabel('L’environnement WSL associé au projet doit être de la même famille et, pour Debian/Fedora, de la même version cible.');label.setWordWrap(True);l.addWidget(label);l.addStretch();self.family_box.currentTextChanged.connect(self.change_family);self.release.currentTextChanged.connect(self.invalidate)
    def tab_system(self):
        l=self.page('Système');f=QFormLayout();self.desktop=self.combo();self.kernel=self.combo(['Stable','LTS','Hardened']);self.init=self.combo();self.display=self.combo(['Wayland','X11','Aucun']);self.audio=self.combo(['PipeWire','PulseAudio','ALSA','Aucun']);self.boot=self.combo(['GRUB','Aucun']);self.bootmode=self.combo(['UEFI','BIOS'])
        for name,c in [('Bureau',self.desktop),('Noyau',self.kernel),('Initialisation',self.init),('Affichage',self.display),('Audio',self.audio),('Bootloader',self.boot),('Mode',self.bootmode)]:f.addRow(name,c);c.currentTextChanged.connect(self.invalidate)
        l.addLayout(f);self.flags={}
        for name,default in [('Wi-Fi',True),('Bluetooth',True),('Impression',False),('Firmware',True)]:c=QCheckBox(name);c.setChecked(default);c.toggled.connect(self.invalidate);self.flags[name]=c;l.addWidget(c)
        l.addWidget(self.button('Analyser les dépendances',self.analyze));l.addStretch()
    def tab_apps(self):
        l=self.page('Applications');r=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('Rechercher firefox, vlc, gimp...');self.query.returnPressed.connect(self.search_apps);r.addWidget(self.query);r.addWidget(self.button('Rechercher',self.search_apps));r.addWidget(self.button('Actualiser les dépôts du projet',self.update_project));l.addLayout(r)
        l.addWidget(QLabel('Résultats : double-clic pour ajouter'));self.results=self.table(['Paquet','Version','Description']);self.results.setColumnWidth(0,280);self.results.setColumnWidth(1,160);self.results.cellDoubleClicked.connect(self.add_result);l.addWidget(self.results,3)
        l.addWidget(QLabel('Applications sélectionnées : double-clic pour retirer'));self.selected_apps=self.table(['Paquet']);self.selected_apps.cellDoubleClicked.connect(self.remove_app);l.addWidget(self.selected_apps,1)
        r=QHBoxLayout();self.manual=QLineEdit();self.manual.setPlaceholderText('Nom exact du paquet');r.addWidget(self.manual);r.addWidget(self.button('Ajouter',self.add_manual));l.addLayout(r);self.app_log=QTextEdit();self.app_log.setReadOnly(True);self.app_log.setMaximumHeight(110);l.addWidget(self.app_log)
    def tab_project(self):
        l=self.page('Projet / ISO');self.summary=QLabel('Aucune analyse');self.summary.setWordWrap(True);l.addWidget(self.summary);self.package_table=self.table(['Paquet','Version','Statut','Taille']);self.package_table.setColumnWidth(0,330);self.package_table.setColumnWidth(1,220);self.package_table.setColumnWidth(2,220);self.package_table.setColumnWidth(3,145);l.addWidget(self.package_table,3)
        self.project_log=QTextEdit();self.project_log.setReadOnly(True);l.addWidget(self.project_log,2);r=QHBoxLayout();r.addWidget(self.button('Analyser',self.analyze));r.addWidget(self.button('Créer l’ISO',self.create_iso));l.addLayout(r)
    def tab_wsl(self):
        l=self.page('WSL2 / Prérequis');r=QHBoxLayout();r.addWidget(self.button('Distributions installées',self.refresh_wsl));r.addWidget(self.button('Catalogue WSL',self.refresh_catalog));r.addStretch();l.addLayout(r)
        split=QSplitter(Qt.Orientation.Horizontal);left=QGroupBox('Catalogue');ll=QVBoxLayout(left);self.catalog_table=self.table(['Nom WSL','Description']);self.catalog_table.setColumnWidth(0,200);ll.addWidget(self.catalog_table);ll.addWidget(self.button('Installer la distribution',self.install_wsl));split.addWidget(left)
        right=QGroupBox('Installées');rl=QVBoxLayout(right);self.inst_table=self.table(['Nom WSL']);rl.addWidget(self.inst_table);rl.addWidget(self.button('Supprimer la distribution',self.delete_wsl));split.addWidget(right);split.setSizes([680,450]);l.addWidget(split,2)
        r=QHBoxLayout();r.addWidget(QLabel('WSL à gérer :'));self.wsl_box=self.combo();r.addWidget(self.wsl_box,1);r.addWidget(self.button('Tester le gestionnaire',self.test_wsl));r.addWidget(self.button('Vérifier les prérequis ISO',self.check_prereq));r.addWidget(self.button('Installer les prérequis',self.install_prereq));r.addWidget(self.button('Actualiser les dépôts',self.update_wsl));l.addLayout(r)
        self.prereq_table=self.table(['Outil','Paquet','État']);self.prereq_table.setColumnWidth(0,180);self.prereq_table.setColumnWidth(1,230);l.addWidget(self.prereq_table,1)
        group=QGroupBox('Associations WSL au projet ISO (indépendantes des contrôles ci-dessus)');form=QFormLayout(group);self.mapping_boxes={}
        for family in FAMILIES:
            c=self.combo(['— Non associé —']);c.currentTextChanged.connect(lambda value,f=family:self.associate(f,value));form.addRow(family,c);self.mapping_boxes[family]=c
        l.addWidget(group);self.wsl_log=QTextEdit();self.wsl_log.setReadOnly(True);self.wsl_log.setMaximumHeight(140);l.addWidget(self.wsl_log)
    def change_family(self,*_):
        family=self.family();self.release.blockSignals(True);self.release.clear();self.release.addItems(RELEASES[family]);self.release.blockSignals(False);self.desktop.blockSignals(True);self.desktop.clear();self.desktop.addItems(['Aucun']+list(DESKTOP[family]));self.desktop.blockSignals(False);self.init.blockSignals(True);self.init.clear();self.init.addItems(['OpenRC','systemd'] if family=='Gentoo' else ['SysVinit'] if family=='Slackware' else ['systemd']);self.init.blockSignals(False);self.kernel.setEnabled(family=='Arch Linux');self.kernel.setCurrentText('Stable');self.apps.clear();self.refresh_apps();self.invalidate()
    def associate(self,family,value):self.mapping[family]='' if value=='— Non associé —' else value;self.invalidate()
    def refresh_wsl(self):self.job('installed',(),self.wsl_loaded)
    def wsl_loaded(self,data,error):
        if error:self.wsl_log.setPlainText(error);return
        self.inst=data;self.fill(self.inst_table,[(x,) for x in data]);self.wsl_box.clear();self.wsl_box.addItems(data)
        for family,c in self.mapping_boxes.items():
            old=self.mapping[family];c.blockSignals(True);c.clear();c.addItems(['— Non associé —']+data)
            if old in data:c.setCurrentText(old)
            else:self.mapping[family]=''
            c.blockSignals(False)
        self.wsl_log.setPlainText('Installées : '+(', '.join(data) or 'aucune'))
    def refresh_catalog(self):self.job('catalog',(),self.catalog_loaded)
    def catalog_loaded(self,data,error):
        if error:self.wsl_log.setPlainText(error);return
        rows,raw=data;self.catalog=rows;self.fill(self.catalog_table,rows);self.wsl_log.setPlainText(str(len(rows))+' distributions trouvées.\n'+(raw[:1500] if not rows else 'Sélectionne une distribution à installer.'))
    def install_wsl(self):
        name=self.selected(self.catalog_table)
        if not name or name not in [r[0] for r in self.catalog]:self.warn('Sélectionne une distribution du catalogue.');return
        if name in self.inst:self.warn('Déjà installée.');return
        if self.ask('Installer '+name+' via WSL ?'):self.job('install_wsl',(name,),lambda d,e:self.operation_done('Installation',d,e))
    def delete_wsl(self):
        name=self.selected(self.inst_table)
        if not name:self.warn('Sélectionne une distribution.');return
        typed,ok=QInputDialog.getText(self,'Suppression définitive','Toutes les données Linux de '+name+' seront effacées.\nSaisis exactement : '+name)
        if ok and typed==name and self.ask('Confirmer la suppression IRRÉVERSIBLE de '+name+' ?'):self.job('delete_wsl',(name,),lambda d,e:self.operation_done('Suppression',d,e))
    def operation_done(self,title,data,error):
        if error:self.wsl_log.setPlainText(title+' : '+error);return
        out,err,rc=data;self.wsl_log.setPlainText(title+' (code '+str(rc)+')\n'+out+'\n'+err)
        if rc:self.warn(title+' échouée, voir le journal.')
        else:self.refresh_wsl()
    def current_wsl(self):
        env=self.wsl_box.currentText().strip()
        if not env or env not in self.inst:self.warn('Sélectionne une distribution WSL installée.');return ''
        return env
    def test_wsl(self):
        env=self.current_wsl()
        if env:self.job('detect',(env,),lambda d,e:self.test_done(env,d,e))
    def test_done(self,env,data,error):
        if error:self.wsl_log.setPlainText(error);return
        family,meta=data;self.wsl_log.setPlainText('WSL : '+env+'\nFamille : '+family+'\nVersion : '+meta.get('VERSION_ID','?'))
    def check_prereq(self):
        env=self.current_wsl()
        if env:self.job('prereq',(env,),lambda d,e:self.prereq_done(env,d,e))
    def prereq_done(self,env,data,error):
        if error:self.wsl_log.setPlainText(error);return
        family,meta,rows,extra=data;self.fill(self.prereq_table,rows);self.wsl_log.setPlainText('WSL : '+env+'\nFamille : '+family+'\nVersion : '+meta.get('VERSION_ID','?')+'\n'+extra+'\nOutils manquants : '+(', '.join(r[1] for r in rows if r[2]=='Absent') or 'aucun'))
    def install_prereq(self):
        env=self.current_wsl()
        if not env:return
        if self.ask('Installer les prérequis manquants dans '+env+' ?\n\nDebian : apt-get update + install non interactif.\nFedora : dnf5 -y install.\nArch : pacman -Syu --noconfirm --needed (mise à niveau complète).\n\nGentoo et Slackware : installation automatique désactivée.\nCette opération modifie la distribution WSL.'):self.job('install_prereq',(env,),lambda d,e:self.install_prereq_done(env,d,e))
    def install_prereq_done(self,env,data,error):
        if error:self.wsl_log.setPlainText(error);self.warn('Préparation échouée. Voir le journal.');return
        family,cmd,(out,err,rc)=data;self.wsl_log.setPlainText('Commande : '+cmd+'\nCode : '+str(rc)+'\n'+(out+'\n'+err)[-15000:])
        if rc:self.warn('Installation échouée (code '+str(rc)+').')
        else:self.info('Installation terminée. Relance la vérification des prérequis.')
    def update_wsl(self):
        env=self.current_wsl()
        if env and self.ask('Actualiser '+env+' ?\nPour Arch, cela exécute pacman -Syu (mise à niveau complète).'):self.job('update',(env,),lambda d,e:self.update_done(env,d,e))
    def update_project(self):
        env=self.project_env()
        if not env:self.warn('Associe un environnement WSL au projet.');return
        if self.ask('Actualiser les dépôts de '+env+' ?'):self.job('update',(env,),lambda d,e:self.update_done(env,d,e))
    def update_done(self,env,data,error):
        if error:self.wsl_log.setPlainText(error);return
        family,cmd,(out,err,rc)=data;text='WSL : '+env+'\nFamille : '+family+'\nCommande : '+cmd+'\nCode : '+str(rc)+'\n'+(out+'\n'+err)[-16000:];self.wsl_log.setPlainText(text);self.app_log.setPlainText(text[-4000:]);self.warn('Mise à jour échouée, voir journal.') if rc else self.info('Dépôts actualisés pour '+env)
    def refresh_apps(self):self.fill(self.selected_apps,[(x,) for x in sorted(self.apps)])
    def add_manual(self):
        s=self.manual.text().strip()
        if not SAFE.fullmatch(s):self.warn('Nom de paquet invalide.');return
        self.apps.add(s);self.manual.clear();self.refresh_apps();self.invalidate()
    def add_result(self,row,_):
        item=self.results.item(row,0)
        if item:self.apps.add(item.text());self.refresh_apps();self.invalidate()
    def remove_app(self,row,_):
        item=self.selected_apps.item(row,0)
        if item:self.apps.discard(item.text());self.refresh_apps();self.invalidate()
    def check_project(self):
        env=self.project_env()
        if not env or env not in self.inst:self.warn('Associe une distribution WSL installée dans WSL2.');self.tabs.setCurrentIndex(4);return ''
        return env
    def search_apps(self):
        env=self.check_project();q=self.query.text().strip()
        if not env:return
        if not q or len(q)>70:self.warn('Recherche vide ou trop longue.');return
        family=self.family();rev=self.revision;self.app_log.setPlainText('Recherche en cours dans '+env+'...');self.job('search',(env,family,q),lambda d,e:self.search_done(family,rev,d,e))
    def search_done(self,family,rev,data,error):
        if rev!=self.revision:return
        if error:self.app_log.setPlainText(error);return
        out,err,rc=data;rows=parse_search(family,out);self.fill(self.results,rows);self.app_log.setPlainText(str(len(rows))+' résultats ; code '+str(rc)+'\n'+((err or out)[:3500] if rc or not rows else 'Double-clique pour ajouter.'))
    def packages(self):
        family=self.family();p=set(BASE[family]);p.update(DESKTOP[family].get(self.desktop.currentText(),[]));p.update(AUDIO[family].get(self.audio.currentText(),[]));p.update(self.apps)
        extras={'Debian':{'Wi-Fi':['wpasupplicant'],'Bluetooth':['bluez'],'Impression':['cups'],'Firmware':['firmware-linux-free']},'Fedora':{'Wi-Fi':['NetworkManager-wifi'],'Bluetooth':['bluez'],'Impression':['cups'],'Firmware':['linux-firmware']},'Arch Linux':{'Wi-Fi':['iwd'],'Bluetooth':['bluez'],'Impression':['cups'],'Firmware':['linux-firmware']},'Gentoo':{'Wi-Fi':['net-wireless/iwd'],'Bluetooth':['net-wireless/bluez'],'Impression':['net-print/cups'],'Firmware':['sys-kernel/linux-firmware']},'Slackware':{'Wi-Fi':['wpa_supplicant'],'Bluetooth':['bluez'],'Impression':['cups'],'Firmware':['kernel-firmware']}}
        for flag,check in self.flags.items():
            if check.isChecked():p.update(extras[family].get(flag,[]))
        if family=='Arch Linux':p.discard('linux');p.add({'Stable':'linux','LTS':'linux-lts','Hardened':'linux-hardened'}[self.kernel.currentText()])
        if family=='Gentoo':p.discard('sys-apps/openrc');p.add('sys-apps/openrc' if self.init.currentText()=='OpenRC' else 'sys-apps/systemd')
        return sorted(p)
    def analyze(self):
        env=self.check_project()
        if not env:return
        family=self.family();packages=self.packages();rev=self.revision;self.project_log.setPlainText('Simulation en cours...');self.job('simulate',(env,family,packages),lambda d,e:self.analyze_done(family,packages,rev,d,e))
    def analyze_done(self,family,packages,rev,data,error):
        if rev!=self.revision:return
        if error:self.project_log.setPlainText(error);self.valid=False;return
        out,err,rc=data;valid,status=assessment(family,out,err,rc);self.valid=valid;self.solution=parse_transaction(family,out,packages)
        self.fill(self.package_table,[(name,v['version'],v['status'],human(v['size'])) for name,v in sorted(self.solution.items())]);self.summary.setText(str(len(self.solution))+' paquets affichés | '+status+'\nTaille ISO : '+estimate(self.solution))
        self.project_log.setPlainText('Attention : simulation dans le WSL existant, non exhaustive pour un rootfs Live neuf.\n'+status+'\nCode : '+str(rc)+'\n\n'+out+'\n'+err)
        if not valid:self.warn('La simulation a échoué. Consulte le journal.')
    def create_iso(self):
        family=self.family()
        if family not in ('Debian','Arch Linux'):self.warn('Construction ISO non intégrée pour '+family+'.\nVérification des prérequis disponible dans WSL2.');return
        if not self.valid:self.warn('Effectue une analyse exploitable avant la construction.');return
        env=self.check_project()
        if not env:return
        folder=QFileDialog.getExistingDirectory(self,'Choisir un dossier Windows VIDE pour recevoir l’ISO')
        if not folder:return
        if any(Path(folder).iterdir()):self.warn('Le dossier doit être vide.');return
        if not self.ask('Construire une ISO '+family+' dans '+env+' ?\n\nLes outils doivent être installés (WSL2 > Vérifier les prérequis).\nLa construction se fait dans /var/tmp de WSL puis copie l’ISO sous Windows.\nPrévoir plusieurs Go libres.\nBIOS, UEFI et Ventoy ne sont PAS garantis.'):return
        self.project_log.setPlainText('Construction en cours dans le système de fichiers Linux WSL...');self.job('build',(env,family,self.release.currentText(),self.packages(),folder),self.build_done)
    def build_done(self,data,error):
        if error:self.project_log.setPlainText('ÉCHEC ISO\n'+error);self.warn('Construction échouée. Cause détaillée dans le journal.');return
        files,report=data;self.project_log.setPlainText(json.dumps(files,indent=2,ensure_ascii=False)+'\n\nBIOS/UEFI/Ventoy : non testés.\n\n'+report[-10000:]);self.info('ISO créée. Test de démarrage VM et Ventoy nécessaire.')

if __name__=='__main__':
    app=QApplication(sys.argv);app.setStyle('Fusion');win=App();win.show();sys.exit(app.exec())
