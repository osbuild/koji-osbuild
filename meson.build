project('koji-osbuild', license: 'ASL 2.0')

srcdir = meson.source_root()

hub_plugins_path = get_option('hub-plugins-path')
builder_plugins_path = get_option('builder-plugins-path')

install_data(
  'plugins/hub/osbuild.py',
  install_dir: hub_plugins_path,
)

install_data(
  'plugins/builder/osbuild.py',
  install_dir: builder_plugins_path
)

git = find_program('git')
gitres = run_command(
  git,
  ['--git-dir=@0@/.git'.format(srcdir), 'rev-parse', 'HEAD'],
  check=True
)
commit = gitres.stdout().strip()

archive_name = meson.project_name() + '-' + gitrev
full_archive_name = archive_name + '.tar.gz'
archive = custom_target(
  'tarball',
  command: [
    git,
    '-C', meson.source_root(),
    'archive',
    '-o', join_paths(meson.build_root(), full_archive_name),
    '--prefix', archive_name + '/',
    commit
  ],
  output: full_archive_name,
)

mkdir = find_program('mkdir')
rpmdirs_target = custom_target(
  'rpmdirs',
  command: [
    mkdir, '-p',
    'rpmbuild/BUILD',
    'rpmbuild/RPMS',
    'rpmbuild/SPECS',
    'rpmbuild/SRPMS'],
  output: 'rpmbuild',
)

rpmbuild = find_program('rpmbuild', required: false)

srpm_target = custom_target(
  'srpm',
  command: [
    rpmbuild, '-bs',
    spec_file,
    '--define', '_sourcedir ' + meson.build_root(),
    '--define', '_topdir ' + rpmdirs_target.full_path(),
    '--define', 'commit ' + commit
  ],
  output: 'srpms',
  depends: [archive]
)

rpm_target = custom_target(
  'rpm',
  command: [
    rpmbuild, '-ba',
    spec_file,
    '--define', '_sourcedir ' + meson.build_root(),
    '--define', '_topdir ' + rpmdirs_target.full_path(),
    '--define', 'commit ' + commit
  ],
  output: 'rpms',
  depends: [archive]
)

msg = ['',
  'hub plugins path:      @0@'.format(hub_plugins_path),
  'builder plugins path:  @0@'.format(builder_plugins_path),
  '',
]
message('\n  '.join(msg))
