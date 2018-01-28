#!/usr/bin/env python

from bs4 import BeautifulSoup as bs
from collections import namedtuple
import fileinput
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib

llvm_version = '5.0.1'
Package = namedtuple('Package', ['name', 'md5sum', 'docset_name',
                                 'docset_api_name', 'src_dir', 'single_pages',
                                 'index_pages'])
SinglePage = namedtuple('SinglePage', ['name', 'type', 'path'])
IndexPage = namedtuple('IndexPage', ['type', 'path'])
packages = (Package('llvm',
                    '3a4ec6dcbc71579eeaec7cb157fe2168',
                    # Dash doesn't like additional dots in the docset name
                    'LLVM_{0}.docset'.format(llvm_version.split('.')[0]),
                    'LLVM_API_{0}.docset'.format(llvm_version.split('.')[0]),
                    'llvm-{0}'.format(llvm_version),
                    [
                        SinglePage('CommandLine 2.0 Library Manual', 'Library',
                                   'CommandLine.html'),
                        SinglePage('LLVM Coding Standards', 'Guide',
                                   'CodingStandards.html'),
                        SinglePage('LLVM Style RTTI', 'Guide',
                                   'HowToSetUpLLVMStyleRTTI.html'),
                        SinglePage('YAML I/O Library', 'Library',
                                   'YamlIO.html')
                    ],
                    [
                        IndexPage('Instruction', 'ProgrammersManual.html'),
                        IndexPage('Category', 'LangRef.html'),
                        IndexPage('Command', 'CommandGuide/index.html'),
                        IndexPage('Guide', 'GettingStarted.html'),
                        IndexPage('Sample', 'tutorial/index.html'),
                        IndexPage('Service', 'Passes.html')
                    ]),
            Package('clang',
                    'e4daa278d8f252585ab73d196484bf11',
                    # Dash doesn't like additional dots in the docset name
                    'Clang_{0}.docset'.format(llvm_version.split('.')[0]),
                    'Clang_API_{0}.docset'.format(llvm_version.split('.')[0]),
                    'llvm-{0}/tools/clang'.format(llvm_version),
                    [
                        SinglePage('Clang Language Extensions''',
                                   'Instruction', 'LanguageExtensions.html'),
                        SinglePage('Address Sanitizer', 'Instruction',
                                   'AddressSanitizer.html'),
                        SinglePage('Thread Sanitizer', 'Instruction',
                                   'ThreadSanitizer.html'),
                        SinglePage('Memory Sanitizer', 'Instruction',
                                   'MemorySanitizer.html'),
                        SinglePage('UB Sanitizer', 'Instruction',
                                   'UndefinedBehaviorSanitizer.html'),
                        SinglePage('Data Flow Sanitizer', 'Instruction',
                                   'DataFlowSanitizer.html'),
                        SinglePage('Leak Sanitizer', 'Instruction',
                                   'LeakSanitizer.html'),
                        SinglePage('Source Based Coverage', 'Instruction',
                                   'SourceBasedCodeCoverage.html'),
                        SinglePage('Modules', 'Instruction', 'Modules.html'),
                        SinglePage('LibTooling', 'Library', 'LibTooling.html'),
                        SinglePage('LibFormat', 'Library', 'LibFormat.html'),
                        SinglePage('ClangFormat Options', 'Instruction',
                                   'ClangFormatStyleOptions.html')
                    ],
                    [
                        IndexPage('Instruction', 'InternalsManual.html'),
                        IndexPage('Instruction', 'UsersManual.html'),
                        IndexPage('Command', 'CommandGuide/index.html')
                    ]))

online_docpath = 'releases.llvm.org/{0}/docs'.format(llvm_version)
docset_path_template = '{0}/Contents/Resources/Documents'


class change_dir(object):
    def __init__(self, path):
        self.cwd_dir = os.getcwd()
        self.new_dir = path

    def __enter__(self):
        os.chdir(self.new_dir)

    def __exit__(self, *args):
        os.chdir(self.cwd_dir)


def clean():
    for package in packages:
        if os.path.exists(package.docset_name):
            shutil.rmtree(package.docset_name)
        if os.path.exists(package.docset_api_name):
            shutil.rmtree(package.docset_api_name)
        if os.path.exists('build'):
            shutil.rmtree('build')


def tarball_name(package_name):
    name = 'cfe' if package_name == 'clang' else package_name
    return '{name}-{version}.src.tar.xz'.format(name=name,
                                                version=llvm_version)


def md5(fname):
    hash = hashlib.md5()
    with open(fname) as f:
        for chunk in iter(lambda: f.read(4096), ''):
            hash.update(chunk)
    return hash.hexdigest()


def check_tarball(name, expected_md5sum):
    md5sum = md5(name)
    if md5sum != expected_md5sum:
        print md5sum
    return md5sum == expected_md5sum


def download_tarballs():
    for package in packages:
        name = tarball_name(package.name)
        if os.access(name, os.R_OK):
            if check_tarball(name, package.md5sum):
                print 'using existing tarball'
                continue
            print 'removing unusable tarball'
            os.remove(name)

        tarball_url = 'http://llvm.org/releases/%s/%s' % (llvm_version, name)
        print 'downloading %s from %s' % (name, tarball_url)
        urllib.urlretrieve(tarball_url, name)

        if not check_tarball(name, package.md5sum):
            raise IOError('{name} src md5sum check failed'.format(name=name))


def get_executable(name):
    def is_exe(exe_path):
        return os.path.isfile(exe_path) and os.access(exe_path, os.X_OK)

    for exe in ['g{0}'.format(name), name]:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_path = os.path.join(path, exe)
            if is_exe(exe_path):
                return exe_path

    raise IOError('''Couldn't find '{0}' executable'''.format(name))


def extract_tarballs():
    tar_exe = get_executable('tar')
    for package in packages:
        src_tarball = tarball_name(package.name)
        if os.path.exists(package.src_dir):
            shutil.rmtree(package.src_dir)
        os.makedirs(package.src_dir)
        subprocess.check_call([tar_exe, '-xf', src_tarball,
                               '-C', package.src_dir, '--strip-components=1'])


def make_target(makefile, target=None, build_dir=None):
    args = [
        'make',
        '-C', os.path.dirname(makefile),
        '-f', os.path.basename(makefile)
    ]

    if target:
        args.append(target)

    if build_dir:
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        args.extend(['BUILDDIR={0}'.format(os.path.abspath(build_dir))])

    print(' '.join(args))
    subprocess.check_call(args)


def update_db(db, cur, name, typ, path):
    try:
        cur.execute('SELECT path, name FROM searchIndex WHERE path = ?', (path,))
        dbpath = cur.fetchone()
        cur.execute('SELECT path, name FROM searchIndex WHERE name = ?', (name,))
        dbname = cur.fetchone()

        if dbpath is None and dbname is None:
            cur.execute('INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?,?,?)', (name, typ, path))

    except:
        pass


def add_pages(db, cur, package):
    def is_relevant(path):
        irrelevant_paths = ('http', 'index.html')
        return (path is not None and len(name) > 2
                and not path.startswith(irrelevant_paths))

    def resolve(path):
        if path.startswith('../'):
            return path[3:]

        if path.startswith('#'):
            return page.path.split('/')[-1] + path

        return path

    for page in package.single_pages:
        update_db(db, cur, page.name, page.type, page.path)

    docset_path = docset_dir(docset_path_template.format(package.docset_name))
    for page in package.index_pages:
        html_path = os.path.join(docset_path, page.path)
        html = open(html_path, 'r').read()
        soup = bs(html, 'lxml')
        for link in soup.findAll('a'):
            name = link.text.strip().replace('\n', '')
            path = link.get('href')

            if (is_relevant(path)):
                update_db(db, cur, name, page.type, resolve(path))


def add_infoplist(docset_name):
    name = docset_name.split('.')[0]
    info = '''<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE plist PUBLIC '-//Apple//DTD PLIST 1.0//EN' 'http://www.apple.com/DTDs/PropertyList-1.0.dtd'>
<plist version='1.0'>
<dict>
    <key>CFBundleIdentifier</key>
    <string>{0}</string>
    <key>CFBundleName</key>
    <string>{0}</string>
    <key>DocSetPlatformFamily</key>
    <string>{0}</string>
    <key>isDashDocset</key>
    <true/>
    <key>isJavaScriptEnabled</key>
    <true/>
    <key>dashIndexFilePath</key>
    <string>index.html</string>
    <key>DashDocSetFallbackURL</key>
    <string>http://{1}/</string>
</dict>
</plist>'''.format(name, online_docpath)
    open(docset_name + '/Contents/Info.plist', 'wb').write(info)


def generate_documentation(package):
    build_dir = os.path.join('build',
                             '{0}-{1}-docs'.format(package.name, llvm_version))

    make_target(os.path.join(package.src_dir, 'docs', 'Makefile.sphinx'),
                build_dir=build_dir)

    docset_dir = docset_path_template.format(package.docset_name)
    os.makedirs(os.path.dirname(docset_dir))
    os.rename(os.path.join(build_dir, 'html'), docset_dir)


def generate_documentation_docsets():
    for package in packages:
        generate_documentation(package)

        shutil.copyfile('icon.png', package.docset_name + '/icon.png')

        db = sqlite3.connect(package.docset_name + '/Contents/Resources/docSet.dsidx')
        cur = db.cursor()
        cur.execute('CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT);')
        cur.execute('CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path);')

        add_pages(db, cur, package)
        add_infoplist(package.docset_name)

        db.commit()
        db.close()


def patch_doxygen_config():
    for package in packages:
        doxygen_cfg = os.path.join(package.src_dir, 'docs', 'doxygen.cfg.in')
        for line in fileinput.input(doxygen_cfg, inplace=True):
            if line.startswith('GENERATE_DOCSET'):
                sys.stdout.write('GENERATE_DOCSET = YES\n')
            elif line.startswith('PROJECT_NAME'):
                name = 'LLVM' if package.name == 'llvm' else 'Clang'
                sys.stdout.write('PROJECT_NAME = {name} {version} C++ API\n'
                                 .format(name=name, version=llvm_version))
            elif line.startswith('LOOKUP_CACHE_SIZE'):
                sys.stdout.write('LOOKUP_CACHE_SIZE = 3\n')
            elif line.startswith('DOCSET_BUNDLE_ID'):
                sys.stdout.write('DOCSET_BUNDLE_ID = org.llvm.{name}\n'
                                 .format(name=package.name.lower()))
            elif line.startswith('ECLIPSE_DOC_ID'):
                sys.stdout.write('ECLIPSE_DOC_ID = org.llvm.{name}\n'
                                 .format(name=package.name.lower()))
            else:
                sys.stdout.write(line)


def fix_docset_plist(package):
    plist_path = os.path.join(package.docset_name, 'Contents', 'Info.plist')
    for line in fileinput.input(plist_path, inplace=True):
        if '<string>doxygen</string>' in line:
            sys.stdout.write('<string>{name}-api</string>\n'
                             .format(name=package.name.lower()))
        else:
            sys.stdout.write(line)


def generate_api_docset(package, src_dir, build_dir):
    doxygen_makefile = os.path.join(build_dir, 'Makefile')
    doxygen_target = 'doxygen-{name}'.format(name=package.name)
    make_target(doxygen_makefile, doxygen_target)

    package_path_parts = package.src_dir.split(os.sep)[1:]
    package_path = ''
    if package_path_parts:
        os.path.join(*package_path_parts)
    html_dir = os.path.join(build_dir, package_path,
                            'docs', 'doxygen', 'html')

    make_target(os.path.join(html_dir, 'Makefile'))

    shutil.move(os.path.join(html_dir, 'org.doxygen.Project.docset'),
                package.docset_api_name)
    shutil.copyfile('icon.png',
                    os.path.join(package.docset_api_name, 'icon.png'))

    fix_docset_plist(package)


def generate_api_docsets():
    patch_doxygen_config()

    src_dir = os.path.join(os.getcwd(),
                           [p.src_dir for p in packages if p.name == 'llvm'][0])
    build_dir = os.path.join('build', 'doxygen-{0}'.format(llvm_version))
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    with change_dir(build_dir):
        subprocess.check_call(['cmake', '-DLLVM_ENABLE_DOXYGEN=ON', src_dir])

    for package in packages:
        if package.name == 'clang':
            generate_api_docset(package, src_dir, build_dir)


def compress_docsets():
    for package in packages:
        shutil.make_archive(package.docset_name, 'gztar',
                            os.getcwd(), package.docset_name)
        shutil.make_archive(package.docset_api_name, 'gztar',
                            os.getcwd(), package.docset_api_name)


def generate_docsets():
    generate_documentation_docsets()
    generate_api_docsets()
    compress_docsets()


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    clean()

    download_tarballs()
    extract_tarballs()

    generate_docsets()
