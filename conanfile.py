from conans import ConanFile, tools, VisualStudioBuildEnvironment, AutoToolsBuildEnvironment
import os
import glob
import shutil

#
# Refer to http://userguide.icu-project.org/icudata for the data_packaging option
#
# Note that the default MSVC builds (msvc_platform=visual_studio) with Visual Studio cannot do static ICU builds
#
# Using the with_data option fetches the complete ICU data package, at the expense of size
#
# If you're building with Cygwin, the environment variable CYGWIN_ROOT must be present or specified via the command line
#
# If you're building with MSYS, the environment variable MSYS_ROOT must be present or specified via the command line
#
# examples:
#
# To update the conanfile.py without rebuilding:
#
#    conan export icu/59.1@cygwin/icu -k && conan package icu/59.1@cygwin/icu addc9b54f567a693944ffcc56568c29b0d0926c8
#
# for creating a tgz:
#
#    conan upload --skip_upload icu/59.1@cygwin/icu -p addc9b54f567a693944ffcc56568c29b0d0926c8
#
# Create an ICU package using a Cygwin/MSVC static release built
#   
#    conan create cygwin/icu -o icu:msvc_platform=cygwin -o icu:shared=False -e CYGWIN_ROOT=D:\PortableApps\CygwinPortable\App\Cygwin
#
# Create an ICU package using a Cygwin/MSYS static debug built
#   
#    conan create cygwin/icu -o icu:msvc_platform=cygwin -s icu:build_type=Debug -o icu:shared=False
#
# Create an ICU package using a Cygwin/MSYS static debug built
#   
#    conan create msys/icu -o icu:msvc_platform=msys -o icu:with_data=True -e MSYS_ROOT=D:\dev\msys64
#

class IcuConan(ConanFile):
    name = "icu"
    version = "59.1"
    license="http://www.unicode.org/copyright.html#License"
    description = "ICU is a mature, widely used set of C/C++ and Java libraries providing Unicode and Globalization support for software applications."
    url = "https://github.com/bincrafters/conan-icu"
    settings = "os", "arch", "compiler", "build_type"
    source_url = "http://download.icu-project.org/files/icu4c/{0}/icu4c-{1}-src".format(version,version.replace('.', '_'))
    data_url = "http://download.icu-project.org/files/icu4c/{0}/icu4c-{1}-data".format(version,version.replace('.', '_'))

    options = {"with_io": [True, False],
               "with_data": [True, False],
               "shared": [True, False],
               "msvc_platform": ["visual_studio", "cygwin", "msys"],
               "data_packaging": ["shared", "static", "files", "archive"],
               "with_unit_tests": [True, False],
               "silent": [True, False]}

    default_options = "with_io=False", \
                      "with_data=False", \
                      "shared=False", \
                      "msvc_platform=visual_studio", \
                      "data_packaging=archive", \
                      "with_unit_tests=False", \
                      "silent=True"
                      
        
    def source(self):
        archive_type = "zip"
        if self.settings.os != 'Windows' or self.options.msvc_platform != 'visual_studio':
            archive_type = "tgz"

        self.output.info("Fetching sources: {0}.{1}".format(self.source_url, archive_type))
        
        tools.get("{0}.{1}".format(self.source_url, archive_type))
        tools.download(r'http://git.savannah.gnu.org/gitweb/?p=config.git;a=blob_plain;f=config.guess;hb=HEAD', 'config.guess');
        tools.download(r'http://git.savannah.gnu.org/gitweb/?p=config.git;a=blob_plain;f=config.sub;hb=HEAD', 'config.sub');
            
        if self.options.with_data:
            tools.get("{0}.zip".format(self.data_url))

    def build(self):
        root_path = self.conanfile_directory
        src_path = os.path.join(root_path, self.name, 'source')
    
        if self.options.with_data:
            # We add the whole data within the source tree
            src_datadir = os.path.join(root_path,'data')
            dst_datadir = os.path.join(src_path, 'data')
        
            os.rename(dst_datadir, dst_datadir + "-bak")
            os.rename(src_datadir,dst_datadir)
        else:
            tools.replace_in_file(
                os.path.join(src_path,'data','makedata.mak'),
                r'GODATA "$(ICU_LIB_TARGET)" "$(TESTDATAOUT)\testdata.dat"',
                r'GODATA "$(ICU_LIB_TARGET)"')
        
        # to be improved        
        src_config_guess = os.path.join(root_path,'config.guess')
        src_config_sub = os.path.join(root_path,'config.sub')
        
        dst_config_guess = os.path.join(root_path, self.name, 'source', 'config.guess')
        dst_config_sub = os.path.join(root_path, self.name, 'source', 'config.sub')
        
        if os.path.isfile(dst_config_guess):
            os.remove(dst_config_guess)
            
        if os.path.isfile(dst_config_sub):
            os.remove(dst_config_sub)
            
        shutil.copy(src_config_guess, dst_config_guess)
        shutil.copy(src_config_sub, dst_config_sub)

        self.output.info("Copy src: " + src_config_guess)
        self.output.info("Copy dst: " + dst_config_guess)
        self.output.info("Copy src: " + src_config_sub)
        self.output.info("Copy dst: " + dst_config_sub)

        # This handles the weird case of using ICU sources for Windows on a Unix environment, and vice-versa
        # this is primarily aimed at builds using Cygwin/MSVC which require unix line endings
        if self.settings.os == 'Windows' and self.options.msvc_platform == 'visual_studio':
            if b'\r\n' not in open(os.path.join(src_path, "runConfigureICU"), 'rb').read():
                self.output.error("\n\nBuild failed. The line endings of your sources are inconsistent with the build configuration you requested. {0} / {1} \
                                   \nPlease consider clearing your cache sources (i.e. remove the --keep-sources command line option\n\n".format(self.settings.os, self.options.msvc_platform))
                return
        #else:
        #    if b'\r\n' not in open(os.path.join(src_path, "runConfigureICU"), 'rb').read():
        #        self.output.error("\n\nBuild failed. The line endings of your sources are inconsistent with the build configuration you requested. {0} / {1} \
        #                           \nPlease consider clearing your cache sources (i.e. remove the --keep-sources command line option\n\n".format(self.settings.os, self.options.msvc_platform))
        #        return
        
        silent = '--silent' if self.options.silent else 'VERBOSE=1'
        general_opts = '--disable-layout --disable-layoutex'
        
        if self.settings.os == 'Windows':
            vcvars_command = tools.vcvars_command(self.settings)
            if self.options.msvc_platform == 'cygwin':
                platform = 'Cygwin/MSVC'

                arch = '64' if self.settings.arch == 'x86_64' else '32'
                enable_debug = '--enable-debug --disable-release' if self.settings.build_type == 'Debug' else ''
                enable_static = '--enable-static --disable-shared' if not self.options.shared else '--enable-shared --disable-static'
                data_packaging = '--with-data-packaging={0}'.format(self.options.data_packaging)

                if not self.options.shared:
                    self.cpp_info.defines.append("U_STATIC_IMPLEMENTATION")

                # try to detect if Cygwin is available
                if 'CYGWIN_ROOT' in os.environ:
                    if not os.path.isdir(os.path.join(os.environ["CYGWIN_ROOT"], "bin")):
                        self.output.error('Cygwin cannot be found on your system. To build ICU with Cygwin/MSVC you need a Cygwin installation (see http://cygwin.com/).')
                        return
                else:
                    if os.path.isdir(r'C:\\Cygwin'):
                        self.output.info(r'Detected an installation of Cygwin in C:\\Cygwin')
                        os.environ["CYGWIN_ROOT"] = r'C:\\Cygwin'
                
                if 'CYGWIN_ROOT' not in os.environ:
                    self.output.warn('CYGWIN_ROOT not in your environment')
                else:
                    self.output.info("Using Cygwin from: " + os.environ["CYGWIN_ROOT"]) 
                
                cygwin_root_path = os.environ["CYGWIN_ROOT"].replace('\\', '/')
                
                os.environ["PATH"] = r"C:\\Windows\\system32" + ";" + \
                                     r"C:\\Windows" + ";" + \
                                     r"C:\\Windows\\system32\Wbem" + ";" +  \
                                     cygwin_root_path + "/bin" + ";" + \
                                     cygwin_root_path + "/usr/bin" + ";" + \
                                     cygwin_root_path + "/usr/sbin"
                
                output_path = os.path.join(root_path, 'output')
                root_path = root_path.replace('\\', '/')
                src_path = src_path.replace('\\', '/')
                output_path = output_path.replace('\\', '/')

                b_path = os.path.join(root_path, self.name, 'build')
                os.mkdir(b_path)
                                
                self.output.info("Starting configuration.")
                self.run("{0} && cd {1} && bash ../source/runConfigureICU {2} {3} --with-library-bits={4} --prefix={5} {6} {7} {general}".format(
                        vcvars_command, b_path, enable_debug, platform, arch, output_path, enable_static, data_packaging, general=general_opts))
                self.output.info("Starting built.")
                # do not use multiple CPUs with make (make -j X) as builds fail on Cygwin
                self.run("{vcenv} && cd {build_path} && make {silent_var}".format(vcenv=vcvars_command, build_path=b_path, silent_var=silent))
                if self.options.with_unit_tests:
                    self.run("{vcenv} && cd {build_path} && make {silent_var} check".format(vcenv=vcvars_command, build_path=b_path, silent_var=silent))
                self.run("{vcenv} && cd {build_path} && make {silent_var} install".format(vcenv=vcvars_command, build_path=b_path, silent_var=silent))
            elif self.options.msvc_platform == 'msys':
                platform = 'MSYS/MSVC'
                
                arch = '64' if self.settings.arch == 'x86_64' else '32'
                enable_debug = '--enable-debug --disable-release' if self.settings.build_type == 'Debug' else ''
                enable_static = '--enable-static --disable-shared' if not self.options.shared else '--enable-shared --disable-static'
                data_packaging = '--with-data-packaging={0}'.format(self.options.data_packaging)
                    
                if not self.options.shared:
                    self.cpp_info.defines.append("U_STATIC_IMPLEMENTATION")
                
                # try to detect if MSYS is available
                if 'MSYS_ROOT' in os.environ:
                    if not os.path.isdir(os.path.join(os.environ["MSYS_ROOT"], 'usr', 'bin')):
                        self.output.error('MSYS cannot be found on your system. To build ICU with MSYS/MSVC you need an MSYS installation (see http://www.msys2.org).')
                        return
                else:
                    if os.path.isdir(r'C:\\msys64'):
                        self.output.info(r'Detected an installation of MSYS in C:\\msys64')
                        os.environ["MSYS_ROOT"] = r'C:\\msys64'
                
                if 'MSYS_ROOT' not in os.environ:
                    self.output.warn('MSYS_ROOT not in your environment')
                else:
                    self.output.info("Using MSYS from: " + os.environ["MSYS_ROOT"]) 
                
                msys_root_path = os.environ["MSYS_ROOT"].replace('\\', '/')

                self.output.info("MSYS_ROOT: " + os.environ["MSYS_ROOT"])
                self.output.info("msys_root_path: " + msys_root_path)
                self.output.info("msys_root_path/bin: " + os.path.join(msys_root_path,'usr','bin'))

                os.environ["PATH"] = r"C:\\Windows\\system32" + ";" + r"C:\\Windows" + ";" + r"C:\\Windows\\system32\Wbem" + ";" + os.path.join(msys_root_path,'usr','bin')
                self.output.info("PATH: " + os.environ["PATH"])
                output_path = os.path.join(root_path, 'output')
                root_path = root_path.replace('\\', '/')
                src_path = src_path.replace('\\', '/')
                output_path = tools.unix_path(output_path)
                #output_path.replace('\\', '/')

                b_path = os.path.join(root_path, self.name, 'build')
                b_path = b_path.replace('\\', '/')
                os.mkdir(b_path)

                apply_msys_config_detection_patch = '--host=i686-pc-mingw{0}'.format(arch)
                
                # If you enable the stuff below => builds may start to stall when building x86/static/Debug
                #env_build = AutoToolsBuildEnvironment(self)
                #if self.settings.build_type == 'Debug':
                #    env_build.cxx_flags.append("-FS")
                    
                #with tools.environment_append(env_build.vars):                    
                self.run("{0} && bash -c ^'cd {1} ^&^& ../source/runConfigureICU {2} {3} {4} --with-library-bits={5} --prefix={6} {7} {8} {general}^'".format(vcvars_command, b_path, enable_debug, platform, apply_msys_config_detection_patch, arch, output_path, enable_static, data_packaging, general=general_opts))

                # There is a fragment in Makefile.in:22 of ICU that prevents from building with MSYS:
                #
                # ifneq (@platform_make_fragment_name@,mh-cygwin-msvc)
                # SUBDIRS += escapesrc
                # endif
                #
                # We patch the respective Makefile.in, to disable building it for MSYS
                #
                escapesrc_patch = os.path.join(root_path, self.name,'source','tools','Makefile.in')
                tools.replace_in_file(escapesrc_patch, 'SUBDIRS += escapesrc', '\tifneq (@platform_make_fragment_name@,mh-msys-msvc)\n\t\tSUBDIRS += escapesrc\n\tendif')

                cpus = tools.cpu_count() if self.settings.build_type == 'Release' else '1'
                
                self.run("{vcenv} && bash -c ^'cd {build_path} ^&^& make {silent_var} -j {cpus_var}".format(vcenv=vcvars_command, build_path=b_path, silent_var=silent, cpus_var=cpus))
                if self.options.with_unit_tests:
                    self.run("{vcenv} && bash -c ^'cd {build_path} ^&^& make {silent_var} check".format(vcenv=vcvars_command, build_path=b_path, silent_var=silent))

                self.run("{vcenv} && bash -c ^'cd {build_path} ^&^& make {silent_var} install'".format(vcenv=vcvars_command, build_path=b_path, silent_var=silent))
            else:
                sln_file = os.path.join(src_path,"allinone","allinone.sln")
                targets = ["i18n","common","pkgdata"]
                if self.options.with_io:
                    targets.append('io')
                build_command = tools.build_sln_command(self.settings, sln_file, targets=targets, upgrade_project=False)
                build_command = build_command.replace('"x86"','"Win32"')
                command = "{0} && {1}".format(vcvars_command, build_command)
                self.run(command)
                cfg = 'x64' if self.settings.arch == 'x86_64' else 'x86'
                cfg += "\\"+str(self.settings.build_type)
                data_dir = src_path+"\\data"
                bin_dir = data_dir+"\\..\\..\\bin"
                if self.settings.arch == 'x86_64':
                    bin_dir += '64'
                makedata = '{vcvars} && cd {datadir} && nmake /a /f makedata.mak ICUMAKE="{datadir}" CFG={cfg}'.format(
                    vcvars=vcvars_command,
                    datadir=data_dir,
                    cfg=cfg)
                self.output.info(makedata)
                self.run(makedata)
        else:
            env_build = AutoToolsBuildEnvironment(self)
            with tools.environment_append(env_build.vars):
                platform = ''
                if self.settings.os == 'Linux':
                    if self.settings.compiler == 'gcc':
                        platform = 'Linux/gcc'
                    else:
                        platform = 'Linux'
                elif self.settings.os == 'Macos':
                    platform = 'MacOSX'
                
                arch = '64' if self.settings.arch == 'x86_64' else '32'
                enable_debug = '--enable-debug --disable-release' if self.settings.build_type == 'Debug' else ''
                enable_static = '--enable-static --disable-shared' if not self.options.shared else '--enable-shared --disable-static'
                data_packaging = '--with-data-packaging={0}'.format(self.options.data_packaging)

                b_path = os.path.join(root_path, self.name, 'build')
                os.mkdir(b_path)

                output_path = os.path.join(root_path, 'output')
                
                # do not move this from here
                runConfigureICU_file = os.path.join(root_path, self.name,'source','runConfigureICU')
                tools.replace_in_file(runConfigureICU_file, '        CC=gcc; export CC\n', '', strict=True)
                tools.replace_in_file(runConfigureICU_file, '        CXX=g++; export CXX\n', '', strict=True)                

                self.run("cd {0} && bash ../source/runConfigureICU {1} {2} --with-library-bits={3} --prefix={4} {5} {6} {general}".format(b_path, 
                                                                                                                                          enable_debug, 
                                                                                                                                          platform, 
                                                                                                                                          arch, 
                                                                                                                                          output_path, 
                                                                                                                                          enable_static, 
                                                                                                                                          data_packaging, 
                                                                                                                                          general=general_opts))
                    
                self.run("cd {build_path} && make {silent_var} -j {cpus_var}".format(build_path=b_path, cpus_var=tools.cpu_count(), silent_var=silent))
                   
                if self.options.with_unit_tests:
                    self.run("cd {build_path} && make {silent_var} check".format(build_path=b_path, silent_var=silent))
                    
                self.run("cd {build_path} && make install".format(build_path=b_path, cpus_var=tools.cpu_count(), silent_var=silent))

                if self.settings.os == 'Macos':
                    with tools.chdir('output/lib'):
                        for dylib in glob.glob('*icu*.{0}.dylib'.format(self.version)):
                            self.run('install_name_tool -id {0} {1}'.format(
                                os.path.basename(dylib), dylib))

    def package(self):
        if self.settings.os == 'Windows':
            bin_dir_dst, lib_dir_dst = ('bin64', 'lib64') if self.settings.arch == 'x86_64' else ('bin' , 'lib')
            if self.options.msvc_platform == 'cygwin' or self.options.msvc_platform == 'msys' or self.options.msvc_platform == 'any':
                if self.options.msvc_platform == 'cygwin':
                    platform = 'Cygwin/MSVC'

                if self.options.msvc_platform == 'msys':
                    platform = 'MSYS/MSVC'

                bin_dir, include_dir, lib_dir, share_dir = (os.path.join('output', path) for path in ('bin', 'include', 'lib', 'share'))
                #self.output.info('bin_dir = {0}'.format(bin_dir))
                #self.output.info('include_dir = {0}'.format(include_dir))
                #self.output.info('lib_dir = {0}'.format(lib_dir))
                #self.output.info('share_dir = {0}'.format(share_dir))
                
                # we copy everything for a full ICU package
                self.copy("*", dst=bin_dir_dst, src=bin_dir, keep_path=True, symlinks=True)
                self.copy(pattern='*.dll', dst=bin_dir_dst, src=lib_dir, keep_path=False)
                
                self.copy("*", dst="include", src=include_dir, keep_path=True, symlinks=True)
                self.copy("*", dst=lib_dir_dst, src=lib_dir, keep_path=True, symlinks=True)
                self.copy("*", dst="share", src=share_dir, keep_path=True, symlinks=True)
            else:
                include_dir, bin_dir, lib_dir = (os.path.join(self.name, path) for path in ('include', bin_dir, lib_dir))
                self.output.info('include_dir = {0}'.format(include_dir))
                self.output.info('bin_dir = {0}'.format(bin_dir))
                self.output.info('lib_dir = {0}'.format(lib_dir))
                self.copy(pattern='*.h', dst='include', src=include_dir, keep_path=True)
                self.copy(pattern='*.lib', dst='lib', src=lib_dir, keep_path=False)
                self.copy(pattern='*.exp', dst='lib', src=lib_dir, keep_path=False)
                self.copy(pattern='*.dll', dst='lib', src=bin_dir, keep_path=False)
        else:
            #libs = ['i18n', 'uc', 'data']
            #if self.options.with_io:
            #    libs.append('io')
            #for lib in libs:
            #    self.copy(pattern="*icu{0}*.dylib".format(lib), dst="lib", src=lib_dir, keep_path=False, symlinks=True)
            #    self.copy(pattern="*icu{0}.so*".format(lib), dst="lib", src=lib_dir, keep_path=False, symlinks=True)

            bin_dir, include_dir, lib_dir, share_dir = (os.path.join('output', path) for path in
                                                        ('bin', 'include', 'lib', 'share'))
            self.output.info('bin_dir = {0}'.format(bin_dir))
            self.output.info('include_dir = {0}'.format(include_dir))
            self.output.info('lib_dir = {0}'.format(lib_dir))
            self.output.info('share_dir = {0}'.format(share_dir))

            # we copy everything for a full ICU package
            self.copy("*", dst="bin", src=bin_dir, keep_path=True, symlinks=True)
            self.copy("*", dst="include", src=include_dir, keep_path=True, symlinks=True)
            self.copy("*", dst="lib", src=lib_dir, keep_path=True, symlinks=True)
            self.copy("*", dst="share", src=share_dir, keep_path=True, symlinks=True)

    def package_id(self):
        # Whether we built with Cygwin or MSYS shouldn't affect the package id
        if self.options.msvc_platform == "cygwin" or self.options.msvc_platform == "msys" or self.options.msvc_platform == "visual_studio":
            self.info.options.msvc_platform = "visual_studio"

        # ICU unit testing shouldn't affect the package's ID
        self.info.options.with_unit_tests = "any"

        # Verbosity doesn't affect package's ID
        self.info.options.silent = "any"
            
    def package_info(self):
    
        bin_dir, lib_dir = ('bin64', 'lib64') if self.settings.arch == 'x86_64' and self.settings.os == 'Windows' else ('bin' , 'lib')
        
        self.cpp_info.libdirs = [ lib_dir ]
        
        self.cpp_info.libs = []
        vtag = self.version.split('.')[0]
        keep = False
            
        for lib in tools.collect_libs(self, lib_dir):
            if not vtag in lib:
                #self.output.info("OUTPUT LIBRARY: " + lib)
                if lib != 'icudata':
                    self.cpp_info.libs.append(lib)
                else:
                    keep = True

        # if icudata is not last, it fails to build on some platforms
        # (have to double-check this)
        if keep:
            self.cpp_info.libs.append('icudata')

        self.env_info.PATH.append(os.path.join(self.package_folder, bin_dir))

        if not self.options.shared:
            self.cpp_info.defines.append("U_STATIC_IMPLEMENTATION")
            if self.settings.os == 'Linux':
                self.cpp_info.libs.append('dl')
                
            if self.settings.os == 'Windows':
                self.cpp_info.libs.append('advapi32')
                
        if self.settings.compiler == "gcc":
            self.cpp_info.cppflags = ["-std=c++11"]
