from conans import ConanFile, tools, AutoToolsBuildEnvironment
import os
import glob
import shutil
import re

#
# Refer to http://userguide.icu-project.org/icudata for the data_packaging option
#
# Note that Visual Studio (sln) builds have been removed, since they cannot generate static builds.
# The default platform for building MSVC binaries is MSYS (msvc_platform=msys)
#
# examples:
#
# To update the conanfile.py without rebuilding:
#
#    conan export icu/60.1@sigmoidal/testing -k && conan package icu/60.1@sigmoidal/testing addc9b54f567a693944ffcc56568c29b0d0926c8
#
# for creating a tgz:
#
#    conan upload --skip_upload icu/60.1@sigmoidal/testing -p addc9b54f567a693944ffcc56568c29b0d0926c8
#
# Create an ICU package using a Cygwin/MSVC static release built
#   
#    conan create sigmoidal/testing -o icu:msvc_platform=cygwin -o icu:shared=False
#
# Create an ICU package using a Cygwin/MSYS static debug built
#   
#    conan create sigmoidal/testing -o icu:msvc_platform=cygwin -s icu:build_type=Debug -o icu:shared=False
#
# Create an ICU package using a Cygwin/MSYS static debug built
#   
#    conan create sigmoidal/testing
#


class IcuConan(ConanFile):
    name = "icu"
    version = "60.1"
    license="http://www.unicode.org/copyright.html#License"
    description = "ICU is a mature, widely used set of C/C++ and Java libraries " \
                  "providing Unicode and Globalization support for software applications."
    url = "https://github.com/sigmoidal/conan-icu"
    settings = "os", "arch", "compiler", "build_type"
    source_url = "http://download.icu-project.org/" \
                 "files/icu4c/{0}/icu4c-{1}-src".format(version,version.replace('.', '_'))
    data_url = "http://download.icu-project.org/" \
               "files/icu4c/{0}/icu4c-{1}-data".format(version,version.replace('.', '_'))

    options = {"shared": [True, False],
               "data_packaging": ["shared", "static", "files", "archive"],
               "with_unit_tests": [True, False],
               "silent": [True, False]}

    default_options = "shared=False", \
                      "data_packaging=archive", \
                      "with_unit_tests=False", \
                      "silent=True"
    
    # Dictionary storing strings useful for setting up the configuration and make command lines
    cfg = {'enable_debug': '',
           'platform': '',
           'host': '',
           'arch_bits': '',
           'output_dir': '',
           'enable_static': '',
           'data_packaging': '',
           'general_opts': ''}

    def source(self):
        self.output.info("Fetching sources: {0}.tgz".format(self.source_url))
        
        tools.get("{0}.tgz".format(self.source_url))
        
        src_folder = os.getcwd()

        # update the outdated config.guess and config.sub included in ICU
        # ICU Ticket: http://bugs.icu-project.org/trac/ticket/13470
        config_updates = ['config.guess', 'config.sub']
        for cfg_update in config_updates:
            dst_config = os.path.join(src_folder, self.name, 'source', cfg_update)
            if os.path.isfile(dst_config):
                os.remove(dst_config)
            self.output.info('Updating %s' % dst_config)
            tools.download('http://git.savannah.gnu.org/gitweb/?p=config.git;'
                           'a=blob_plain;f={0};hb=HEAD'.format(cfg_update), dst_config)
        
        #
        # ICU has incomplete data in the tgz file released,
        # need to download and merge them separately.
        # http://bugs.icu-project.org/trac/ticket/13139
        #
        data_web_file = "{0}.zip".format(self.data_url)
        self.output.info('Fetching data: %s' % data_web_file)
        tools.get(data_web_file)

        icu_datadir = os.path.join(src_folder, self.name, 'source', 'data')
        downloaded_icu_datadir = os.path.join(src_folder,'data')

        shutil.rmtree(icu_datadir)
        os.rename(downloaded_icu_datadir, icu_datadir)

        # Download and apply patch for ICU Ticket: http://bugs.icu-project.org/trac/ticket/13469
        patchfile = 'icu-60.1-msvc-escapesrc.patch'
        tools.download('http://bugs.icu-project.org/trac/'
                       'raw-attachment/ticket/13469/%s' % patchfile, patchfile)
        tools.patch(base_path=os.path.join(src_folder, self.name), patch_file=patchfile, strip=1)

    def build(self):

        if self.settings.os == 'Windows':
            runtime = str(self.settings.compiler.runtime)

        if self.settings.os == 'Windows':
            run_config_icu_file = os.path.join(self.name, 'source','runConfigureICU')

            if self.settings.build_type == 'Release':
                tools.replace_in_file(run_config_icu_file, "-MD", "-%s" % runtime)
            if self.settings.build_type == 'Debug':
                tools.replace_in_file(run_config_icu_file, "-MDd", "-%s -FS" % runtime)
        else:
            # This allows building ICU with multiple gcc compilers
            # (overrides fixed compiler name gcc, i.e. gcc-5)
            run_config_icu_file = os.path.join(self.name, 'source', 'runConfigureICU')
            tools.replace_in_file(run_config_icu_file,
                                  '        CC=gcc; export CC\n', '', strict=True)
            tools.replace_in_file(run_config_icu_file,
                                  '        CXX=g++; export CXX\n', '', strict=True)

        self.cfg['icu_source_dir'] = os.path.join(self.build_folder, self.name, 'source')
        self.cfg['build_dir'] = os.path.join(self.build_folder, self.name, 'build')
        self.cfg['output_dir'] = os.path.join(self.build_folder, 'output')

        self.cfg['silent'] = '--silent' if self.options.silent else 'VERBOSE=1'
        self.cfg['enable_debug'] = '--enable-debug --disable-release' \
            if self.settings.build_type == 'Debug' else ''
        self.cfg['arch_bits'] = '64' if self.settings.arch == 'x86_64' else '32'
        self.cfg['enable_static'] = '--enable-static --disable-shared' \
            if not self.options.shared else '--enable-shared --disable-static'
        self.cfg['data_packaging'] = '--with-data-packaging={0}'.format(self.options.data_packaging) 
        self.cfg['general_opts'] = '--disable-layout --disable-layoutex'
                
        if not self.options.shared:
            self.cpp_info.defines.append("U_STATIC_IMPLEMENTATION")

        if self.settings.os == 'Windows':
            # this overrides pre-configured environments (such as Appveyor's)
            if "VisualStudioVersion" in os.environ:
                del os.environ["VisualStudioVersion"]
            self.cfg['vccmd'] = tools.vcvars_command(self.settings)

            if self.options.msvc_platform == 'cygwin':
                self.build_cygwin()
            elif self.options.msvc_platform == 'msys':
                self.build_msys()
        else:
            self.build_unix()

    def package(self):
        bin_dir_src, include_dir_src, lib_dir_src, share_dir_src = (os.path.join('output', path) for path in
                                                                    ('bin', 'include', 'lib', 'share'))
        if self.settings.os == 'Windows':
            bin_dir_dst, lib_dir_dst = ('bin64', 'lib64') if self.settings.arch == 'x86_64' else ('bin', 'lib')

            # we copy everything for a full ICU package
            self.copy("*", dst=bin_dir_dst, src=bin_dir_src, keep_path=True, symlinks=True)
            self.copy(pattern='*.dll', dst=bin_dir_dst, src=lib_dir_src, keep_path=False)
            self.copy("*", dst=lib_dir_dst, src=lib_dir_src, keep_path=True, symlinks=True)

            # lets remove .dlls from the lib dir, they are in bin/ in upstream releases.
            if os.path.exists(os.path.join(self.package_folder, lib_dir_dst)):
                for item in os.listdir(os.path.join(self.package_folder, lib_dir_dst)):
                    if item.endswith(".dll"):
                        os.remove(os.path.join(self.package_folder, lib_dir_dst, item))

            self.copy("*", dst="include", src=include_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="share", src=share_dir_src, keep_path=True, symlinks=True)
        else:
            # we copy everything for a full ICU package
            self.copy("*", dst="bin", src=bin_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="include", src=include_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="lib", src=lib_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="share", src=share_dir_src, keep_path=True, symlinks=True)

    def package_id(self):
        # Whether we built with Cygwin or MSYS shouldn't affect the package id
        if self.options.msvc_platform == "cygwin" or self.options.msvc_platform == "msys":
            self.info.options.msvc_platform = "any"

        # ICU unit testing shouldn't affect the package's ID
        self.info.options.with_unit_tests = "any"

        # Verbosity doesn't affect package's ID
        self.info.options.silent = "any"
            
    def package_info(self):
        bin_dir, lib_dir = ('bin64', 'lib64') \
            if self.settings.arch == 'x86_64' and self.settings.os == 'Windows' else ('bin', 'lib')
        
        self.cpp_info.libdirs = [lib_dir]
        
        self.cpp_info.libs = []
        vtag = self.version.split('.')[0]
        keep = False
        for lib in tools.collect_libs(self, lib_dir):
            if not vtag in lib:
                if lib != 'icudata':
                    self.cpp_info.libs.append(lib)
                else:
                    keep = True

        # if icudata is not last, it fails to build on some platforms (Windows)
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

    def build_config_cmd(self):
        outdir = self.cfg['output_dir']

        if self.options.msvc_platform == 'msys':
            outdir = tools.unix_path(self.cfg['output_dir'])
        if self.options.msvc_platform == 'cygwin':
            outdir = re.sub(r'([a-z]):(.*)',
                            '/cygdrive/\\1\\2',
                            self.cfg['output_dir'],
                            flags=re.IGNORECASE).replace('\\', '/')

        config_cmd = "../source/runConfigureICU {enable_debug} " \
                     "{platform} {host} {lib_arch_bits} {outdir} " \
                     "{enable_static} {data_packaging} {general}" \
                     "".format(enable_debug=self.cfg['enable_debug'],
                               platform=self.cfg['platform'],
                               host=self.cfg['host'],
                               lib_arch_bits='--with-library-bits=%s' % self.cfg['arch_bits'],
                               outdir='--prefix=%s' % outdir,
                               enable_static=self.cfg['enable_static'],
                               data_packaging=self.cfg['data_packaging'],
                               general=self.cfg['general_opts'])

        return config_cmd

    def build_msys(self):
        # self.cfg['platform'] = 'MSYS/MSVC'

        # if 'MSYS_ROOT' not in os.environ:
        #    os.environ['MSYS_ROOT'] = self.deps_env_info["msys2_installer"].MSYS_ROOT

        # if 'MSYS_ROOT' not in os.environ:
        #     raise Exception("MSYS_ROOT environment variable must be set.")
        # else:
        #     self.output.info("Using MSYS from: " + os.environ["MSYS_ROOT"])

        # os.environ['PATH'] = os.path.join(os.environ['MSYS_ROOT'], 'usr', 'bin') + os.pathsep + \
        #                      os.environ['PATH']

        os.mkdir(self.cfg['build_dir'])

        self.cfg['host'] = '--host=i686-pc-mingw{0}'.format(self.cfg['arch_bits'])

        config_cmd = self.build_config_cmd()

        with tools.chdir(self.cfg['build_dir']):

            def run_bash(cmd):
                self.run("{vccmd} && bash -c ^'{cmd}^'".format(vccmd=self.cfg['vccmd'],
                                                               cmd=cmd))
            run_bash(config_cmd)
            run_bash("make {silent} -j {cpus_var}".format(silent=self.cfg['silent'],
                                                          cpus_var=tools.cpu_count()))
            if self.options.with_unit_tests:
                run_bash("make %s check" % self.cfg['silent'])

            run_bash("make %s install'" % self.cfg['silent'])

    def build_cygwin(self):
        self.cfg['platform'] = 'Cygwin/MSVC'

        if 'CYGWIN_ROOT' not in os.environ:
            os.environ['CYGWIN_ROOT'] = self.deps_env_info["cygwin_installer"].CYGWIN_ROOT

        if 'CYGWIN_ROOT' not in os.environ:
            raise Exception("CYGWIN_ROOT environment variable must be set.")
        else:
            self.output.info("Using Cygwin from: " + os.environ["CYGWIN_ROOT"])

        os.environ['PATH'] = os.path.join(os.environ['CYGWIN_ROOT'], 'bin') + os.pathsep + \
                             os.path.join(os.environ['CYGWIN_ROOT'], 'usr', 'bin') + os.pathsep + \
                             os.environ['PATH']

        os.mkdir(self.cfg['build_dir'])
        with tools.chdir(self.cfg['build_dir']):
            self.output.info("Starting configuration.")

            def run_with_vcmd(cmd):
                self.run("{vccmd} && {cmd}".format(vccmd=self.cfg['vccmd'], cmd=cmd))

            config_cmd = self.build_config_cmd()
            run_with_vcmd("bash -c '{config_cmd}'".format(config_cmd=config_cmd))
            self.output.info("Starting built.")

            run_with_vcmd("make {silent} -j {cpus_var}".format(silent=self.cfg['silent'],
                                                               cpus_var=tools.cpu_count()))
            if self.options.with_unit_tests:
                run_with_vcmd("make {silent} check".format(silent=self.cfg['silent']))

            run_with_vcmd("make {silent} install".format(silent=self.cfg['silent']))

    def build_unix(self):
        env_build = AutoToolsBuildEnvironment(self)
        with tools.environment_append(env_build.vars):
            if self.settings.os == 'Linux':
                self.cfg['platform'] = 'Linux/gcc' if str(self.settings.compiler).startswith('gcc') else 'Linux'
            elif self.settings.os == 'Macos':
                self.cfg['platform'] = 'MacOSX'

            os.mkdir(self.cfg['build_dir'])

            config_cmd = self.build_config_cmd()

            # with tools.environment_append(env_build.vars):
            with tools.chdir(self.cfg['build_dir']):
                self.run("bash {config_cmd}".format(config_cmd=config_cmd))

                self.run("make {silent} -j {cpus_var}".format(cpus_var=tools.cpu_count(),
                                                              silent=self.cfg['silent']))

                if self.options.with_unit_tests:
                    self.run("make {silent} check".format(silent=self.cfg['silent']))

                self.run("make {silent} install".format(silent=self.cfg['silent']))

            if self.settings.os == 'Macos':
                with tools.chdir('output/lib'):
                    for dylib in glob.glob('*icu*.{0}.dylib'.format(self.version)):
                        self.run('install_name_tool -id {0} {1}'.format(
                            os.path.basename(dylib), dylib))
