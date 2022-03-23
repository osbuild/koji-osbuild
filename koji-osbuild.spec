# Do not build with tests by default
# Pass --with tests to rpmbuild to override
%bcond_with tests

%global         forgeurl https://github.com/osbuild/koji-osbuild

Name:           koji-osbuild
Version:        5
Release:        0%{?dist}
Summary:        Koji integration for osbuild composer

%forgemeta

License:        ASL 2.0
URL:            %{forgeurl}
Source0:        %{forgesource}

BuildArch:      noarch
BuildRequires:  python%{python3_pkgversion}-devel
BuildRequires:  python%{python3_pkgversion}dist(setuptools)

%description
Koji integration for osbuild composer.

%package        hub
Summary:        Koji hub plugin for osbuild composer integration
Requires:       %{name} = %{version}-%{release}
Requires:       koji-hub
Requires:       python3-jsonschema

%description    hub
Koji hub plugin for osbuild composer integration.

%package        builder
Summary:        Koji hub plugin for osbuild composer integration
Requires:       %{name} = %{version}-%{release}
Requires:       koji-builder
Requires:       python3-requests

%description    builder
Koji builder plugin for osbuild composer integration.

%package        cli
Summary:        Koji client plugin for osbuild composer integration
Requires:       %{name} = %{version}-%{release}
Requires:       koji

%description    cli
Koji client plugin for osbuild composer integration.

%prep
%forgesetup

%build
# no op

%install
install -d %{buildroot}/%{_prefix}/lib/koji-hub-plugins
install -p -m 0755 plugins/hub/osbuild.py %{buildroot}/%{_prefix}/lib/koji-hub-plugins/
%py_byte_compile %{__python3} %{buildroot}/%{_prefix}/lib/koji-hub-plugins/osbuild.py

install -d %{buildroot}/%{_prefix}/lib/koji-builder-plugins
install -p -m 0755 plugins/builder/osbuild.py %{buildroot}/%{_prefix}/lib/koji-builder-plugins/
%py_byte_compile %{__python3} %{buildroot}/%{_prefix}/lib/koji-builder-plugins/osbuild.py

install -d %{buildroot}%{python3_sitelib}/koji_cli_plugins
install -p -m 0644 plugins/cli/osbuild.py %{buildroot}%{python3_sitelib}/koji_cli_plugins/osbuild.py
%py_byte_compile %{__python3} %{buildroot}%{python3_sitelib}/koji_cli_plugins/osbuild.py


%if %{with tests}
# Tests
install -m 0755 -vd                                             %{buildroot}/%{_libexecdir}/tests/%{name}
install -m 0755 -vp test/integration.sh                         %{buildroot}/%{_libexecdir}/tests/%{name}/

install -m 0755 -vd                                             %{buildroot}/%{_libexecdir}/%{name}-tests
install -m 0755 -vp test/make-certs.sh                          %{buildroot}/%{_libexecdir}/%{name}-tests/
install -m 0755 -vp test/build-container.sh                     %{buildroot}/%{_libexecdir}/%{name}-tests/
install -m 0755 -vp test/run-koji-container.sh                  %{buildroot}/%{_libexecdir}/%{name}-tests/
install -m 0755 -vp test/run-openid.sh                          %{buildroot}/%{_libexecdir}/%{name}-tests/
install -m 0755 -vp test/copy-creds.sh                          %{buildroot}/%{_libexecdir}/%{name}-tests/
install -m 0755 -vp test/run-builder.sh                         %{buildroot}/%{_libexecdir}/%{name}-tests/
install -m 0755 -vp test/make-tags.sh                           %{buildroot}/%{_libexecdir}/%{name}-tests/

install -m 0755 -vd                                             %{buildroot}/%{_libexecdir}/%{name}-tests/integration
install -m 0755 -vp test/integration/*                          %{buildroot}/%{_libexecdir}/%{name}-tests/integration/

install -m 0755 -vd                                             %{buildroot}/%{_datadir}/%{name}-tests

install -m 0755 -vd                                             %{buildroot}/%{_datadir}/%{name}-tests/data
install -m 0755 -vp test/data/*                                 %{buildroot}/%{_datadir}/%{name}-tests/data/

install -m 0755 -vd                                             %{buildroot}/%{_datadir}/%{name}-tests/container
install -m 0755 -vp test/container/brew.repo                    %{buildroot}/%{_datadir}/%{name}-tests/container/

install -m 0755 -vd                                             %{buildroot}/%{_datadir}/%{name}-tests/container/builder
install -m 0755 -vp test/container/builder/Dockerfile.fedora    %{buildroot}/%{_datadir}/%{name}-tests/container/builder/
install -m 0755 -vp test/container/builder/Dockerfile.rhel      %{buildroot}/%{_datadir}/%{name}-tests/container/builder/
install -m 0755 -vp test/container/builder/kojid.conf           %{buildroot}/%{_datadir}/%{name}-tests/container/builder/
install -m 0755 -vp test/container/builder/osbuild-koji.conf    %{buildroot}/%{_datadir}/%{name}-tests/container/builder/
install -m 0755 -vp test/container/builder/osbuild.krb5.conf    %{buildroot}/%{_datadir}/%{name}-tests/container/builder/
install -m 0755 -vp test/container/builder/run-kojid.sh         %{buildroot}/%{_datadir}/%{name}-tests/container/builder/

install -m 0755 -vd                                             %{buildroot}/%{_datadir}/%{name}-tests/container/hub
install -m 0755 -vp test/container/hub/Dockerfile.fedora        %{buildroot}/%{_datadir}/%{name}-tests/container/hub/
install -m 0755 -vp test/container/hub/Dockerfile.rhel          %{buildroot}/%{_datadir}/%{name}-tests/container/hub/
install -m 0755 -vp test/container/hub/hub.conf                 %{buildroot}/%{_datadir}/%{name}-tests/container/hub/
install -m 0755 -vp test/container/hub/kojiweb.conf             %{buildroot}/%{_datadir}/%{name}-tests/container/hub/
install -m 0755 -vp test/container/hub/run-hub.sh               %{buildroot}/%{_datadir}/%{name}-tests/container/hub/
install -m 0755 -vp test/container/hub/ssl.conf                 %{buildroot}/%{_datadir}/%{name}-tests/container/hub/
install -m 0755 -vp test/container/hub/web.conf                 %{buildroot}/%{_datadir}/%{name}-tests/container/hub/

install -m 0755 -vd                                             %{buildroot}/%{_datadir}/%{name}-tests/container/hub/plugin
install -m 0755 -vp test/container/hub/plugin/osbuild.py        %{buildroot}/%{_datadir}/%{name}-tests/container/hub/

%endif

%files
%license LICENSE
%doc README.md

%files hub
%{_prefix}/lib/koji-hub-plugins/osbuild.py
%{_prefix}/lib/koji-hub-plugins/__pycache__/osbuild.*

%files builder
%{_prefix}/lib/koji-builder-plugins/osbuild.py
%{_prefix}/lib/koji-builder-plugins/__pycache__/osbuild.*

%files cli
%{python3_sitelib}/koji_cli_plugins/osbuild.py
%{python3_sitelib}/koji_cli_plugins/__pycache__/osbuild.*

%if %{with tests}

%package tests
Summary:        Integration tests for koji-osbuild
Requires:       %{name} = %{version}-%{release}
Requires:       %{name}-cli
Requires:       container-selinux
Requires:       dnsmasq
Requires:       jq
Requires:       koji
Requires:       krb5-workstation
Requires:       openssl
Requires:       osbuild-composer >= 22
Requires:       osbuild-composer-tests
Requires:       podman
Requires:       podman-plugins

# See comment in test/integration.sh
%if 0%{?fedora}
Requires:       podman-plugins
%endif

%description tests
Integration tests for koji-osbuild. To be run on a dedicated system.

%files tests
%{_libexecdir}/tests/%{name}
%{_libexecdir}/%{name}-tests
%{_datadir}/%{name}-tests

%endif


%changelog
# the changelog is distribution-specific, therefore there's just one entry
# to make rpmlint happy.

* Tue Aug 25 2020 Image Builder team <osbuilders@osbuild.org> - 0-1
- On this day, this project was born.
