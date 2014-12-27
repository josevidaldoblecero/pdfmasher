#!/usr/bin/env python3
# Created By: Virgil Dupras
# Created On: 2011-06-20
# Copyright 2013 Hardcoded Software (http://www.hardcoded.net)
#
# This software is licensed under the "GPL v3" License as described in the "LICENSE" file,
# which should be included with this package. The terms are also available at
# http://www.hardcoded.net/licenses/gplv3_license

import os
import os.path as op
import compileall
import shutil
import json
from argparse import ArgumentParser
import platform

from hscommon.build import (copy_packages, build_debian_changelog, copy_qt_plugins, print_and_do,
    get_module_version, setup_package_argparser, package_cocoa_app_in_dmg, move)
from hscommon.plat import ISLINUX, ISWINDOWS
from hscommon.util import find_in_path

def parse_args():
    parser = ArgumentParser()
    setup_package_argparser(parser)
    return parser.parse_args()

def package_windows(dev):
    from cx_Freeze import Freezer, Executable
    app_version = get_module_version('core')
    if op.exists('dist'):
        shutil.rmtree('dist')

    is64bit = platform.architecture()[0] == '64bit'
    exe = Executable(
        targetName = 'PdfMasher.exe',
        script = 'run.py',
        base = 'Win32GUI',
        icon = 'images\\main_icon.ico',
    )
    freezer = Freezer(
        [exe],
        # Since v4.2.3, cx_freeze started to falsely include tkinter in the package. We exclude it explicitly because of that.
        excludes = ['tkinter'],
    )
    freezer.Freeze()

    # Now we have to copy pdfminder's cmap to our root dist dir (We'll set CMAP_PATH env at runtime)
    import pdfminer.cmap
    cmap_src = op.dirname(pdfminer.cmap.__file__)
    cmap_dest = op.join('dist', 'cmap')
    shutil.copytree(cmap_src, cmap_dest)

    if not dev:
        # Copy qt plugins
        plugin_dest = op.join('dist', 'qt4_plugins')
        plugin_names = ['accessible', 'codecs', 'iconengines', 'imageformats']
        copy_qt_plugins(plugin_names, plugin_dest)

        # Compress with UPX
        if not is64bit: # UPX doesn't work on 64 bit
            libs = [name for name in os.listdir('dist') if op.splitext(name)[1] in ('.pyd', '.dll', '.exe')]
            for lib in libs:
                print_and_do("upx --best \"dist\\{0}\"".format(lib))

    help_path = 'build\\help'
    print("Copying {0} to dist\\help".format(help_path))
    shutil.copytree(help_path, 'dist\\help')
    if is64bit:
        # In 64bit mode, we don't install the VC redist as a prerequisite. We just bundle the
        # appropriate dlls.
        shutil.copy(find_in_path('msvcr100.dll'), 'dist')
        shutil.copy(find_in_path('msvcp100.dll'), 'dist')

    if not dev:
        # AdvancedInstaller.com has to be in your PATH
        # this is so we don'a have to re-commit installer.aip at every version change
        installer_file = 'qt\\installer64.aip' if is64bit else 'qt\\installer.aip'
        shutil.copy(installer_file, 'installer_tmp.aip')
        print_and_do('AdvancedInstaller.com /edit installer_tmp.aip /SetVersion {}'.format(app_version))
        print_and_do('AdvancedInstaller.com /build installer_tmp.aip -force')
        os.remove('installer_tmp.aip')


def copy_cource_files(destpath, packages):
    if op.exists(destpath):
        shutil.rmtree(destpath)
    os.makedirs(destpath)
    shutil.copy('run.py', op.join(destpath, 'run.py'))
    copy_packages(packages, destpath)
    shutil.copytree(op.join('build', 'help'), op.join(destpath, 'help'))
    shutil.copy(op.join('images', 'logo_small.png'), destpath)
    shutil.copy(op.join('images', 'logo_big.png'), destpath)
    compileall.compile_dir(destpath)

def package_debian_distribution(distribution):
    app_version = get_module_version('core')
    version = '{}~{}'.format(app_version, distribution)
    destpath = op.join('build', 'pdfmasher-{}'.format(version))
    srcpath = op.join(destpath, 'src')
    copy_cource_files(srcpath, ['qt', 'ebooks', 'hscommon', 'core', 'qtlib', 'pdfminer', 'ply',
        'jobprogress', 'markdown', 'cssutils', 'cssselect', 'encutils'])
    shutil.copytree('debian', op.join(destpath, 'debian'))
    move(op.join(destpath, 'debian', 'Makefile'), op.join(destpath, 'Makefile'))
    build_debian_changelog(op.join('help', 'changelog'), op.join(destpath, 'debian', 'changelog'),
        'pdfmasher', from_version='0.1.0', distribution=distribution)
    shutil.copytree(op.join('build', 'help'), op.join(srcpath, 'help'))
    os.chdir(destpath)
    cmd = "dpkg-buildpackage -S"
    os.system(cmd)
    os.chdir('../..')

def package_debian():
    print("Packaging for Ubuntu")
    for distribution in ['precise', 'quantal']:
        package_debian_distribution(distribution)

def package_arch():
    # For now, package_arch() will only copy the source files into build/. It copies less packages
    # than package_debian because there are more python packages available in Arch (so we don't
    # need to include them).
    print("Packaging for Arch")
    srcpath = op.join('build', 'pdfmasher-arch')
    copy_cource_files(srcpath, ['qt', 'ebooks', 'hscommon', 'core', 'qtlib', 'pdfminer', 'ply',
        'jobprogress'])

def main():
    args = parse_args()
    conf = json.load(open('conf.json'))
    ui = conf['ui']
    dev = conf['dev']
    print("Packaging PdfMasher with UI {0}".format(ui))
    if ui == 'cocoa':
        package_cocoa_app_in_dmg('build/PdfMasher.app', '.', args)
    elif ui == 'qt':
        if ISWINDOWS:
            package_windows(dev)
        elif ISLINUX:
            if not args.arch_pkg:
                distname, _, _ = platform.dist()
            else:
                distname = 'arch'
            if distname == 'arch':
                package_arch()
            else:
                package_debian()
        else:
            print("Qt packaging only works under Windows or Linux.")

if __name__ == '__main__':
    main()
