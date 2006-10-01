#!/usr/bin/perl -w
#
# Monolithic script to modify bootloader configuration.
# Supports GRUB, LILO, ELILO, Yaboot.
# Functions taken from Linux::Bootloader module.

use strict;
use Getopt::Long;

my @bootconfig = [];
my $debug      = 0;
my $bootloader;
my %params;

GetOptions(
    \%params,
    "bootloader-probe",    # Prints the bootloader in use on the system
    "arch-probe",          # Prints the arch of the system
    "bootloader|b=s",
    "config_file=s",
    "add-kernel|a=s",
    "remove-kernel|r=s",
    "update-kernel|u=s",
    "title=s",
    "args=s",
    "remove-args=s",
    "initrd=s",
    "root=s",
    "savedefault=s",
    "position=s",
    "info|i=s",
    "debug|d=i",
    "set-default=s",
    "make-default",
    "force",
    "boot-once",
    "install",
    "default",
    "help",
    "man",
);

&usage if ( !%params || defined $params{help} );


### Detection Functions ###

sub detect_architecture {
    my $arch_style = shift || 'uname';

    my $arch;
    if ( $arch_style eq 'linux' ) {
        $arch = `uname -m | sed -e s/i.86/i386/ -e s/sun4u/sparc64/ -e s/arm.*/arm/ \
	-e s/sa110/arm/ -e s/s390x/s390/ -e s/parisc64/parisc/`;
        chomp $arch;
    }
    elsif ( $arch_style eq 'gentoo' ) {
        $arch = `uname -m | sed -e s/i.86/x86/ -e s/sun4u/sparc/ -e s/arm.*/arm/ \
	-e s/sa110/arm/ -e s/x86_64/amd64/ -e s/sparc.*/sparc/ -e s/parisc.*/hppa/`;
        chomp $arch;
    }
    else {
        $arch = `uname -m`;
        chomp $arch;
    }
    return $arch;
}

sub detect_bootloader {
    return detect_bootloader_from_conf(@_)
      || detect_bootloader_from_mbr(@_);
}

sub detect_bootloader_from_conf {
    my @boot_loader = ();

    my %boot_list = (
        grub   => '/boot/grub/menu.lst',
        lilo   => '/etc/lilo.conf',
        elilo  => '/etc/elilo.conf',
        yaboot => '/etc/yaboot.conf'
    );

    foreach my $key ( sort keys %boot_list ) {
        if ( -f $boot_list{$key} ) {
            push( @boot_loader, $key );
        }
    }

    if ( wantarray() ) {
        return @boot_loader;
    }
    elsif ( @boot_loader == 1 ) {
        return pop(@boot_loader);
    }
    else {
        return undef;
    }
}

sub detect_bootloader_from_mbr {
    my @filelist    = @_;
    my @boot_loader = ();

    my %map = (
        "GRUB"   => 'grub',
        "LILO"   => 'lilo',
        "EFI"    => 'elilo',
        "yaboot" => 'yaboot',
    );

    if ( !@filelist && opendir( DIRH, "/sys/block" ) ) {
        @filelist = grep { /^[sh]d.$/ } readdir(DIRH);
        closedir(DIRH);
    }

    foreach (@filelist) {
        if ( -b "/dev/$_" ) {
            my $strings = `dd if=/dev/$_ bs=512 count=1 2>/dev/null | strings`;
            foreach my $loader ( keys %map ) {
                if ( $strings =~ /$loader/ms ) {
                    push @boot_loader, $map{$loader};
                }
            }
        }
    }

    if ( wantarray() ) {

        # Show them all
        return @boot_loader;
    }
    elsif ( @boot_loader == 1 ) {

        # Found exactly one
        return pop @boot_loader;
    }
    else {

        # Either none or too many to choose from
        return undef;
    }
}

### GRUB functions ###

# Parse config into array of hashes

sub _info_grub {

    return undef unless &_check_config();

    my @config = @bootconfig;
    @config = grep( !/^#|^\n/, @config );

    my %matches = (
        default     => '^\s*default\s*\=*\s*(\S+)',
        timeout     => '^\s*timeout\s*\=*\s*(\S+)',
        fallback    => '^\s*fallback\s*\=*\s*(\S+)',
        kernel      => '^\s*kernel\s+(\S+)',
        root        => '^\s*kernel\s+.*\s+root=(\S+)',
        args        => '^\s*kernel\s+\S+\s+(.*)\n',
        boot        => '^\s*root\s+(.*)',
        initrd      => '^\s*initrd\s+(.*)',
        savedefault => '^\s*savedefault\s+(.*)',
    );

    my @sections;
    my $index = 0;
    foreach (@config) {
        if ( $_ =~ /^\s*title\s+(.*)/i ) {
            $index++;
            $sections[$index]{title} = $1;
        }
        foreach my $key ( keys %matches ) {
            if ( $_ =~ /$matches{$key}/i ) {
                $sections[$index]{$key} = $1;
                if ( $key eq 'args' ) {
                    $sections[$index]{$key} =~ s/root=\S+\s*//i;
                    delete $sections[$index]{$key} if ( $sections[$index]{$key} !~ /\S/ );
                }
            }
        }
    }

    # sometimes config doesn't have a default, so goes to first
    if ( !( defined $sections[0]{'default'} ) ) {
        $sections[0]{'default'} = '0';

        # if default is 'saved', read from grub default file
    }
    elsif ( $sections[0]{'default'} =~ m/^saved$/i ) {
        open( DEFAULT_FILE, '/boot/grub/default' )
          || warn("ERROR:  cannot read grub default file.\n") && return undef;
        my @default_config = <DEFAULT_FILE>;
        close(DEFAULT_FILE);
        $default_config[0] =~ /^(\d+)/;
        $sections[0]{'default'} = $1;
    }

    # return array of hashes
    return @sections;
}

# Set new default kernel

sub set_default_grub {
    my $newdefault = shift;

    return undef unless defined $newdefault;
    return undef unless &_check_config();

    my @config   = @bootconfig;
    my @sections = &_info();

    # if not a number, do title lookup
    if ( $newdefault !~ /^\d+$/ ) {
        $newdefault = &_lookup($newdefault);
    }

    my $kcount = $#sections - 1;
    if (   ( !defined $newdefault )
        || ( $newdefault < 0 )
        || ( $newdefault > $kcount ) )
    {
        warn "ERROR:  Enter a default between 0 and $kcount.\n";
        return undef;
    }

    foreach my $index ( 0 .. $#config ) {
        if ( $config[$index] =~ /(^\s*default\s*\=*\s*)\d+/i ) {
            $config[$index] = "$1$newdefault	# set by $0\n";
            last;
        }
        elsif ( $config[$index] =~ /^\s*default\s*\=*\s*saved/i ) {
            my @default_config;
            my $default_config_file = '/boot/grub/default';

            open( DEFAULT_FILE, $default_config_file )
              || warn("ERROR:  cannot open default file.\n") && return undef;
            @default_config = <DEFAULT_FILE>;
            close(DEFAULT_FILE);

            $default_config[0] = "$newdefault\n";

            open( DEFAULT_FILE, ">$default_config_file" )
              || warn("ERROR:  cannot open default file.\n") && return undef;
            print DEFAULT_FILE join( "", @default_config );
            close(DEFAULT_FILE);
            last;
        }
    }
    @bootconfig = @config;
}

# Add new kernel to config

sub add_grub {
    my %param = @_;

    print("Adding kernel.\n") if &debug() > 1;

    if ( !defined $param{'add-kernel'} || !defined $param{'title'} ) {
        warn "ERROR:  kernel path (--add-kernel), title (--title) required.\n";
        return undef;
    }
    elsif ( !( -f "$param{'add-kernel'}" ) ) {
        warn "ERROR:  kernel $param{'add-kernel'} not found!\n";
        return undef;
    }
    elsif ( defined $param{'initrd'} && !( -f "$param{'initrd'}" ) ) {
        warn "ERROR:  initrd $param{'initrd'} not found!\n";
        return undef;
    }

    return undef unless &_check_config();

    my @sections = &_info();

    # check if title already exists
    if ( defined &_lookup( $param{title} ) ) {
        warn("WARNING:  Title already exists.\n");
        if ( defined $param{force} ) {
            &remove( $param{title} );
        }
        else {
            return undef;
        }
    }

    my @config = @bootconfig;
    @sections = &_info();

    # Use default kernel to fill in missing info
    my $default = &get_default();
    $default++;

    foreach my $p ( 'args', 'root', 'boot', 'savedefault' ) {
        if ( !defined $param{$p} ) {
            $param{$p} = $sections[$default]{$p};
        }
    }

    # use default entry to determine if path (/boot) should be removed
    if ( $sections[$default]{'kernel'} !~ /^\/boot/ ) {
        $param{'add-kernel'} =~ s/^\/boot//;
        $param{'initrd'} =~ s/^\/boot// unless !defined $param{'initrd'};
    }

    my @newkernel;
    push( @newkernel, "title\t$param{title}\n" ) if defined $param{title};
    push( @newkernel, "\troot $param{boot}\n" )  if defined $param{boot};

    my $line;
    $line = "\tkernel $param{'add-kernel'}" if defined $param{'add-kernel'};
    $line = $line . " root=$param{root}"    if defined $param{root};
    $line = $line . " $param{args}"         if defined $param{args};
    push( @newkernel, "$line\n" );

    push( @newkernel, "\tinitrd $param{initrd}\n" ) if defined $param{initrd};
    push( @newkernel, "\tsavedefault $param{savedefault}\n" )
      if defined $param{savedefault};
    push( @newkernel, "\n" );

    if ( !defined $param{position} || $param{position} !~ /end|\d+/ ) {
        $param{position} = 0;
    }

    my @newconfig;
    if ( $param{position} =~ /end/ || $param{position} >= $#sections ) {
        $param{position} = $#sections;
        push( @newconfig, @config );
        if ( $newconfig[$#newconfig] =~ /\S/ ) {
            push( @newconfig, "\n" );
        }
        push( @newconfig, @newkernel );
    }
    else {
        my $index = 0;
        foreach (@config) {
            if ( $_ =~ /^\s*title/i ) {
                if ( $index == $param{position} ) {
                    push( @newconfig, @newkernel );
                }
                $index++;
            }
            push( @newconfig, $_ );
        }
    }

    @bootconfig = @newconfig;

    if ( defined $param{'make-default'} || defined $param{'boot-once'} ) {
        &set_default( $param{position} );
    }
    print "Added: $param{'title'}.\n";
}

# Update kernel args

sub update_grub {
    my %params = @_;

    print("Updating kernel.\n") if &debug() > 1;

    if ( !defined $params{'update-kernel'}
        || ( !defined $params{'args'} && !defined $params{'remove-args'} ) )
    {
        warn
"ERROR:  kernel position or title (--update-kernel) and args (--args or --remove-args) required.\n";
        return undef;
    }

    return undef unless &_check_config();

    my @config   = @bootconfig;
    my @sections = &_info();

    # if not a number, do title lookup
    if ( $params{'update-kernel'} !~ /^\d+$/ ) {
        $params{'update-kernel'} = &_lookup( $params{'update-kernel'} );
    }

    my $kcount = $#sections - 1;
    if (   $params{'update-kernel'} !~ /^\d+$/
        || $params{'update-kernel'} < 0
        || $params{'update-kernel'} > $kcount )
    {
        warn "ERROR:  Enter a default between 0 and $kcount.\n";
        return undef;
    }

    my $index = -1;
    foreach (@config) {
        if ( $_ =~ /^\s*title/i ) {
            $index++;
        }
        if ( $index == $params{'update-kernel'} ) {
            if ( $_ =~ /(^\s*kernel\s+\S+\s+)(.*)\n/i ) {
                my $kernel = $1;
                my $args   = $2;
                $args =~ s/\s+$params{'remove-args'}\=*\S*//ig
                  if defined $params{'remove-args'};
                $args = $args . " " . $params{'args'}
                  if defined $params{'args'};
                if ( $_ eq $kernel . $args . "\n" ) {
                    warn "WARNING:  No change made to args.\n";
                    return undef;
                }
                else {
                    $_ = $kernel . $args . "\n";
                }
                next;
            }
        }
    }
    @bootconfig = @config;
}

# Run command to install bootloader

sub install_grub {
    my $device;

    warn "Re-installing grub is currently unsupported.\n";
    warn
      "If you really need to re-install grub, use 'grub-install <device>'.\n";
    return undef;

    #system("grub-install $device");
    #if ($? != 0) {
    #  warn ("ERROR:  Failed to run grub-install.\n") && return undef;
    #}
    #return 1;
}

### LILO functions ###

# Run command to install bootloader

sub install_lilo {

    system("/sbin/lilo");
    if ( $? != 0 ) {
        warn("ERROR:  Failed to run lilo.\n") && return undef;
    }
    return 1;
}

# Set kernel to be booted once

sub boot_once_lilo {
    my $label = shift;

    return undef unless defined $label;

    if ( system( "lilo", "-R", "$label" ) ) {
        warn("ERROR:  Failed to set boot-once.\n") && return undef;
    }
    return 1;
}

### ELILO functions ###

# Run command to install bootloader

sub install_elilo {

    system("/usr/sbin/elilo");
    if ( $? != 0 ) {
        warn("ERROR:  Failed to run elilo.\n") && return undef;
    }
    return 1;
}

# Set kernel to be booted once

sub boot_once_elilo {
    my $label = shift;

    return undef unless defined $label;

    &read( '/etc/elilo.conf' );
    my @config = @bootconfig;

    if ( ! grep( /^checkalt/i, @config ) ) {
        warn("ERROR:  Failed to set boot-once.\n");
        warn("Please add 'checkalt' to global config.\n");
	return undef;
    }

    my @sections = &_info();
    my $position = &_lookup($label);
    $position++;
    my $efiroot = `grep ^EFIROOT /usr/sbin/elilo | cut -d '=' -f 2`;
    chomp($efiroot);

    my $kernel = $efiroot . $sections[$position]{kernel};
    my $root = $sections[$position]{root};
    my $args = $sections[$position]{args};

    #system( "eliloalt", "-d" );
    if ( system( "eliloalt", "-s", "$kernel root=$root $args" ) ) {
        warn("ERROR:  Failed to set boot-once.\n");
        warn("1) Check that EFI var support is compiled into kernel.\n");
        warn("2) Verify eliloalt works.  You may need to patch it to support sysfs EFI vars.\n");
	return undef;
    }
    return 1;
}


### YABOOT functions ###

# Run command to install bootloader

sub install_yaboot {

    #system("/usr/sbin/ybin");
    #if ( $? != 0 ) {
    #    warn("ERROR:  Failed to run ybin.\n") && return undef;
    #}

    print("Not installing bootloader.\n");
    print("Depending on your arch you may need to run ybin.\n");
    return 1;
}

### Generic Functions ###

# Read config file into array

sub read {
    my $config_file = shift;
    print("Reading $config_file.\n") if debug() > 1;

    open( CONFIG, "$config_file" )
      || warn("ERROR:  Can't open $config_file.\n") && return undef;
    @bootconfig = <CONFIG>;
    close(CONFIG);

    print("Current config:\n @bootconfig") if &debug() > 4;
    print("Closed $config_file.\n")        if &debug() > 2;
    return 1;
}

# Write new config

sub write {
    my $config_file = shift;
    my @config      = @bootconfig;

    return undef unless &_check_config();

    print("Writing $config_file.\n") if &debug() > 1;
    print join( "", @config ) if &debug() > 4;

    if ( -w $config_file ) {
        system( "cp", "$config_file", "$config_file.bak.boottool" );
        if ( $? != 0 ) {
            warn "ERROR:  Cannot backup $config_file.\n";
            return undef;
        } else {
            print "Backed up config to $config_file.bak.boottool.\n";
        }
        open( CONFIG, ">$config_file" )
          || warn("ERROR:  Can't open config file.\n") && return undef;
        print CONFIG join( "", @config );
        close(CONFIG);
        return 0;
    }
    else {
        print join( "", @config ) if &debug() > 2;
        warn "WARNING:  You do not have write access to $config_file.\n";

        return 1;
    }
}

# Parse config into array of hashes

sub _info {

    return &_info_grub() if ( $bootloader eq 'grub' );

    return undef unless &_check_config();
    my @config = @bootconfig;

    # remove garbarge - comments, blank lines
    @config = grep( !/^#|^\n/, @config );

    my %matches = (
        default => '^\s*default[\s+\=]+(\S+)',
        timeout => '^\s*timeout[\s+\=]+(\S+)',
        title   => '^\s*label[\s+\=]+(\S+)',
        root    => '^\s*root[\s+\=]+(\S+)',
        args    => '^\s*append[\s+\=]+(.*)',
        initrd  => '^\s*initrd[\s+\=]+(\S+)',
    );

    my @sections;
    my $index = 0;
    foreach (@config) {
        if ( $_ =~ /^\s*(image|other)[\s+\=]+(\S+)/i ) {
            $index++;
            $sections[$index]{'kernel'} = $2;
        }
        foreach my $key ( keys %matches ) {
            if ( $_ =~ /$matches{$key}/i ) {
                $sections[$index]{$key} = $1;
                $sections[$index]{$key} =~ s/\"|\'//g if ( $key eq 'args' );
            }
        }
    }

    # sometimes config doesn't have a default, so goes to first
    if ( !( defined $sections[0]{'default'} ) ) {
        $sections[0]{'default'} = '0';

        # if default is label name, we need position
    }
    elsif ( $sections[0]{'default'} !~ m/^\d+$/ ) {
        foreach my $index ( 1 .. $#sections ) {
            if ( $sections[$index]{'title'} eq $sections[0]{'default'} ) {
                $sections[0]{'default'} = $index - 1;
                last;
            }
        }
    }

    # if still no valid default, set to first
    if ( $sections[0]{'default'} !~ m/^\d+$/ ) {
        $sections[0]{'default'} = 0;
    }

    # return array of hashes
    return @sections;
}

# Determine current default kernel

sub get_default {

    print("Getting default.\n") if &debug() > 1;
    return undef unless &_check_config();

    my @sections = &_info();
    my $default  = $sections[0]{'default'};

    $default = 0 + $default;
    return ($default);
}

# Set new default kernel

sub set_default {
    my $newdefault = shift;

    return &set_default_grub($newdefault) if ( $bootloader eq 'grub' );

    print("Setting default.\n") if &debug() > 1;

    return undef unless defined $newdefault;
    return undef unless &_check_config();

    my @config   = @bootconfig;
    my @sections = &_info();

    # if not a number, do title lookup
    if ( $newdefault !~ /^\d+$/ ) {
        $newdefault = &_lookup($newdefault);
    }

    my $kcount = $#sections - 1;
    if (   ( !defined $newdefault )
        || ( $newdefault < 0 )
        || ( $newdefault > $kcount ) )
    {
        warn "ERROR:  Enter a default between 0 and $kcount.\n";
        return undef;
    }

    # convert position to title
    $newdefault = $sections[ ++$newdefault ]{title};

    foreach my $index ( 0 .. $#config ) {
        if ( $config[$index] =~ /^\s*default/i ) {
            $config[$index] = "default=$newdefault	# set by $0\n";
            last;
        }
    }
    @bootconfig = @config;
}

# Add new kernel to config

sub add {
    my %param = @_;

    return &add_grub(%param) if ( $bootloader eq 'grub' );

    print("Adding kernel.\n") if &debug() > 1;

    if ( !defined $param{'add-kernel'} || !defined $param{'title'} ) {
        warn "ERROR:  kernel path (--add-kernel), title (--title) required.\n";
        return undef;
    }
    elsif ( !( -f "$param{'add-kernel'}" ) ) {
        warn "ERROR:  kernel $param{'add-kernel'} not found!\n";
        return undef;
    }
    elsif ( defined $param{'initrd'} && !( -f "$param{'initrd'}" ) ) {
        warn "ERROR:  initrd $param{'initrd'} not found!\n";
        return undef;
    }

    return undef unless &_check_config();

    # remove title spaces and truncate if more than 15 chars
    $param{title} =~ s/\s+//g;
    $param{title} = substr( $param{title}, 0, 15 )
      if length( $param{title} ) > 15;

    my @sections = &_info();

    # check if title already exists
    if ( defined &_lookup( $param{title} ) ) {
        warn("WARNING:  Title already exists.\n");
        if ( defined $param{force} ) {
            &remove( $param{title} );
        }
        else {
            return undef;
        }
    }

    my @config = @bootconfig;
    @sections = &_info();

    # Use default kernel to fill in missing info
    my $default = &get_default();
    $default++;

    foreach my $p ( 'args', 'root' ) {
        if ( !defined $param{$p} ) {
            $param{$p} = $sections[$default]{$p};
        }
    }

    # use default entry to determine if path (/boot) should be removed
    if ( $sections[$default]{'kernel'} !~ /^\/boot/ ) {
        $param{'add-kernel'} =~ s/^\/boot//;
        $param{'initrd'} =~ s/^\/boot// unless ( !defined $param{'initrd'} );
    }

    my @newkernel;
    push( @newkernel,
        "image=$param{'add-kernel'}\n",
        "\tlabel=$param{title}\n" );
    push( @newkernel, "\tappend=\"$param{args}\"\n" ) if defined $param{args};
    push( @newkernel, "\tinitrd=$param{initrd}\n" )   if defined $param{initrd};
    push( @newkernel, "\troot=$param{root}\n" )       if defined $param{root};
    push( @newkernel, "\tread-only\n\n" );

    if ( !defined $param{position} || $param{position} !~ /end|\d+/ ) {
        $param{position} = 0;
    }

    my @newconfig;
    if ( $param{position} =~ /end/ || $param{position} >= $#sections ) {
        $param{position} = $#sections;
        push( @newconfig, @config );
        if ( $newconfig[$#newconfig] =~ /\S/ ) {
            push( @newconfig, "\n" );
        }
        push( @newconfig, @newkernel );
    }
    else {
        my $index = 0;
        foreach (@config) {
            if ( $_ =~ /^\s*(image|other)/i ) {
                if ( $index == $param{position} ) {
                    push( @newconfig, @newkernel );
                }
                $index++;
            }
            push( @newconfig, $_ );
        }
    }

    @bootconfig = @newconfig;

    if ( defined $param{'make-default'} ) {
        &set_default( $param{position} );
    }
}

# Update kernel args

sub update {
    my %params = @_;

    return &update_grub(%params) if ( $bootloader eq 'grub' );

    print("Updating kernel.\n") if &debug() > 1;

    if ( !defined $params{'update-kernel'}
        || ( !defined $params{'args'} && !defined $params{'remove-args'} ) )
    {
        warn
"ERROR:  kernel position or title (--update-kernel) and args (--args or --remove-args) required.\n";
        return undef;
    }

    return undef unless &_check_config();

    my @config   = @bootconfig;
    my @sections = &_info();

    # if not a number, do title lookup
    if ( $params{'update-kernel'} !~ /^\d+$/ ) {
        $params{'update-kernel'} = &_lookup( $params{'update-kernel'} );
    }

    my $kcount = $#sections - 1;
    if (   $params{'update-kernel'} !~ /^\d+$/
        || $params{'update-kernel'} < 0
        || $params{'update-kernel'} > $kcount )
    {
        warn "ERROR:  Enter a default between 0 and $kcount.\n";
        return undef;
    }

    my $index = -1;
    foreach (@config) {
        if ( $_ =~ /^\s*(image|other)/i ) {
            $index++;
        }
        if ( $index == $params{'update-kernel'} ) {
            if ( $_ =~ /(^\s*append[\s\=]+)(.*)\n/i ) {
                my $append = $1;
                my $args   = $2;
                $args =~ s/\"|\'//g;
                $args =~ s/\s*$params{'remove-args'}\=*\S*//ig
                  if defined $params{'remove-args'};
                $args = $args . " " . $params{'args'}
                  if defined $params{'args'};
                if ( $_ eq "$append\"$args\"\n" ) {
                    warn "WARNING:  No change made to args.\n";
                    return undef;
                }
                else {
                    $_ = "$append\"$args\"\n";
                }
                next;
            }
        }
    }
    @bootconfig = @config;
}

# Remove kernel from config

sub remove {
    my $position = shift;
    my @newconfig;

    return undef unless defined $position;
    return undef unless &_check_config();

    my @config   = @bootconfig;
    my @sections = &_info();

    if ( $position =~ /^end$/i ) {
        $position = $#sections - 1;
    }
    elsif ( $position =~ /^start$/i ) {
        $position = 0;
    }

    print("Removing kernel $position.\n") if &debug() > 1;

    # remove based on title
    if ( $position !~ /^\d+$/ ) {
        my $removed = 0;
        for ( my $index = $#sections ; $index > 0 ; $index-- ) {
            if ( defined $sections[$index]{title}
                && $position eq $sections[$index]{title} )
            {
                $removed++ if &remove( $index - 1 );
            }
        }
        if ( !$removed ) {
            warn "ERROR:  No kernel with specified title.\n";
            return undef;
        }

        # remove based on position
    }
    elsif ( $position =~ /^\d+$/ ) {

        if ( $position < 0 || $position > $#sections ) {
            warn "ERROR:  Enter a position between 0 and $#sections.\n";
            return undef;
        }

        my $index = -1;
        foreach (@config) {
            if ( $_ =~ /^\s*(image|other|title)/i ) {
                $index++;
            }

            # add everything to newconfig, except removed kernel (keep comments)
            if ( $index != $position || $_ =~ /^#/ ) {
                push( @newconfig, $_ );
            }
        }
        @bootconfig = @newconfig;

        # if we removed the default, set new default to first
        &set_default(0) if $position == $sections[0]{'default'};

        print "Removed kernel $position.\n";
        return 1;

    }
    else {
        warn "WARNING:  problem removing entered position.\n";
        return undef;
    }

}

# Print info from config

sub print_info {
    my $info = shift;

    return undef unless defined $info;
    return undef unless &_check_config();

    print("Printing config info.\n") if &debug() > 1;

    my @config   = @bootconfig;
    my @sections = &_info();

    my ( $start, $end );
    if ( $info =~ /default/i ) {
        $start = $end = &get_default();
    }
    elsif ( $info =~ /all/i ) {
        $start = 0;
        $end   = $#sections - 1;
    }
    elsif ( $info =~ /^\d+/ ) {
        $start = $end = $info;
    }
    else {
        warn "ERROR:  input should be: #, default, or all.\n";
        return undef;
    }

    if ( $start < 0 || $end > $#sections - 1 ) {
        warn "ERROR:  No kernels with that index.\n";
        return undef;
    }

    for my $index ( $start .. $end ) {
        print "\nindex\t: $index\n";
        $index++;
        foreach ( keys( %{ $sections[$index] } ) ) {
            print "$_\t: $sections[$index]{$_}\n";
        }
    }
}

# Attempt to install bootloader

sub install {
    return &install_lilo()   if ( $bootloader eq 'lilo' );
    return &install_grub()   if ( $bootloader eq 'grub' );
    return &install_elilo()  if ( $bootloader eq 'elilo' );
    return &install_yaboot() if ( $bootloader eq 'yaboot' );
}

# Set/get debug level

sub debug {
    if (@_) {
        $debug = shift;
    }
    return $debug;
}

# Basic check for valid config

sub _check_config {

    print("Verifying config.\n") if &debug() > 3;

    if ( $#bootconfig < 5 ) {
        warn "ERROR:  you must read a valid config file first.\n";
        return undef;
    }
    return 1;
}

# lookup position using title

sub _lookup {
    my $title = shift;

    my @sections = &_info();

    for my $index ( 1 .. $#sections ) {
        if (   ( defined $sections[$index]{title} )
            && ( $title eq $sections[$index]{title} ) )
        {
            return $index - 1;
        }
    }
    return undef;
}

### Bootloader / Arch Detection ###

my $detected_bootloader;
my $detected_architecture;

if ( defined $params{'bootloader-probe'} ) {
    $detected_bootloader = detect_bootloader()
      || warn "Could not detect bootloader\n";
    print "$detected_bootloader\n";
    exit 0;
}
elsif ( defined $params{'arch-probe'} ) {
    $detected_architecture = detect_architecture()
      || warn "Could not detect architecture\n";
    print "$detected_architecture\n";
    exit 0;
}
elsif ( defined $params{bootloader} ) {
    $detected_bootloader = $params{bootloader};
}
else {
    $detected_bootloader = detect_bootloader()
      || die "Could not detect bootloader\n";
}

### Do Config ###

$bootloader = $detected_bootloader;

my %cfg_files = (
    grub   => '/boot/grub/menu.lst',
    lilo   => '/etc/lilo.conf',
    elilo  => '/etc/elilo.conf',
    yaboot => '/etc/yaboot.conf'
);

$params{config_file} = $cfg_files{$bootloader}
  unless defined $params{config_file};
die("Can't read config file.\n") unless ( -r $params{config_file} );
&debug( $params{'debug'} ) if ( defined $params{'debug'} );

if ( defined $params{'add-kernel'} ) {
    &read( $params{config_file} );
    &add(%params);
    &write( $params{config_file} );
    &install() unless $detected_bootloader eq 'grub';

}
elsif ( defined $params{'remove-kernel'} ) {
    &read( $params{config_file} );
    &remove( $params{'remove-kernel'} );
    &write( $params{config_file} );
    &install() unless $detected_bootloader eq 'grub';

}
elsif ( defined $params{'update-kernel'} ) {
    &read( $params{config_file} );
    &update(%params);
    &write( $params{config_file} );
    &install() unless $detected_bootloader eq 'grub';

}
elsif ( defined $params{info} ) {
    &read( $params{config_file} );
    &print_info( $params{info} );

}
elsif ( defined $params{'set-default'} ) {
    &read( $params{config_file} );
    &set_default( $params{'set-default'} );
    &write( $params{config_file} );
    &install() unless $detected_bootloader eq 'grub';

}
elsif ( defined $params{'default'} ) {
    &read( $params{config_file} );
    print get_default() . "\n";

}
elsif ( defined $params{'boot-once'} && defined $params{'title'} ) {
    if ( $detected_bootloader eq 'lilo' ) {
        &boot_once_lilo( $params{title} );
    } elsif ( $detected_bootloader eq 'elilo' ) {
        &boot_once_elilo( $params{title} );
    } else {
        print "$detected_bootloader does not have boot-once support.\n";
        print "Setting as default instead.\n";
        &read( $params{config_file} );
        &set_default( $params{'title'} );
        &write( $params{config_file} );
    }
}

sub usage {
    print "Usage:
boottool [--bootloader-probe] [--arch-probe]
         [--add-kernel=<kernel_path>] [--title=<kernel_title>] 
         [--position=<#|start|end>] [--root=<root_path>] 
         [--args=<kernel_args>] [--initrd=<initrd_path>]
         [--make-default] [--force] [--boot-once] [--install]
         [--bootloader=<grub|lilo|elilo|yaboot>] [--config-file=<config_path>]
         [--remove-kernel=<#|title|start|end>]
         [--update-kernel=<#|title>] [--remove-args=<args>]
         [--info=<all|default|#>] [--default] [--set-default=<#>]
         [--help] [--debug=<0..5>]

Examples:
    boottool --info all					# Print config info
    boottool -a /boot/vmlinuz -t 'test' -p end		# Add a new kernel
    boottool --remove-kernel 3				# Remove a kernel
    boottool --set-default 1				# Set new default\n";
    exit 1;
}
