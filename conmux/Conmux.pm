#
# Conmux.pm -- core console multiplexor package
#
# Implements the core multiplexor functionality such as resolution of
# names and connecting to the conmux server.
#
# (C) Copyright IBM Corp. 2004, 2005, 2006
# Author: Andy Whitcroft <andyw@uk.ibm.com>
#
# The Console Multiplexor is released under the GNU Public License V2
#
package Conmux;
use URI::Escape;
use File::Basename;
use Cwd 'abs_path';

our $Config;

BEGIN {
	my $abs_path = abs_path($0);
	my $dir_path = dirname($abs_path);

	my $cf = '/usr/local/conmux/etc/config';
	if (-e "$dir_path/etc/config") {
		$cf = "$dir_path/etc/config";
	} elsif (-e "$dir_path/../etc/config") {
		$cf = "$dir_path/../etc/config";
	}

	if (-f $cf) {
		open(CFG, "<$cf") || die "Conmux: $cf: open failed - $!\n";
		while(<CFG>) {
			chomp;
			next if (/^#/ || /^\s*$/ || !/=/);

			my ($name, $value) = split(/=/, $_, 2);
			$value =~ s/^"//;
			$value =~ s/"$//;

			# Substitute variables.
			while ($value =~ /\$([A-Za-z0-9_]+)/) {
				my $v = $Config->{$1};
				$value =~ s/\$$1/$v/;
			}
			$Config->{$name} = $value;
		}
		close(CFG);
	}
}

sub encodeArgs {
	my (%a) = @_;
	my ($a, $n, $s);

	##print "0<$_[0]> ref<" . ref($_[0]) . ">\n";

	# Handle being passed references to hashes too ...
	$a = \%a;
	$a = $_[0] if (ref($_[0]) eq "HASH");

	for $n (sort keys %{$a}) {
		$s .= uri_escape($n) . '=' . uri_escape($a->{$n}) .
			' ';
	}
	chop($s);
	$s;
}

sub decodeArgs {
	my ($s) = @_;
	my (%a, $nv, $n, $v);

	# Decode the standard argument stream.
	for  $nv (split(' ', $s)) {
		($n, $v) = split('=', $nv, 2);
		$a{uri_unescape($n)} = uri_unescape($v);
	}

	%a;
}

sub sendCmd {
	my ($fh, $c, $a) = @_;
	my ($rs);

	# Send the encoded command ...
	print $fh $c . " " . encodeArgs($a) . "\n";

	# Read the reply.
	$rs = <$fh>;
	chomp($rs);

	decodeArgs($rs);
}

sub sendRequest {
	my ($fh, $c, $a) = @_;
	my %a = { 'result' => 'more' };

	# Send the encoded command ...
	print $fh $c . " " . encodeArgs($a) . "\n";

	%a;
}
sub revcResult {
	my ($fh) = @_;
	my ($rs);

	# Read the reply.
	$rs = <$fh>;
	chomp($rs);

	decodeArgs($rs);
}

#
# Configuration.
#
sub configRegistry {
	my $reg = $Config->{'registry'};

	$reg = "localhost" if (!$reg);
	$reg;
}

# Connect to the host/port specified on the command line,
# or localhost:23
sub connect {
	my ($to) = @_;
	my ($reg, $sock);

	# host:port
	if ($to =~ /:/) {
		# Already in the right form.

	# registry/service
	} elsif ($to =~ m@(.*)/(.*)@) {
		my ($host, $service) = ($1, $2);

		$to = Conmux::Registry::lookup($host, $service);

	# service
	} else {
		$to = Conmux::Registry::lookup('-', $to);
	}

	$sock = new IO::Socket::INET(Proto => 'tcp', PeerAddr => $to)
		or die "Conmux::connect $to: connect failed - $@\n";

	# Turn on keep alives by default.
	$sock->sockopt(SO_KEEPALIVE, 1);

	$sock;
}

package Conmux::Registry;
sub lookup {
	my ($host, $service) = @_;

	$host = Conmux::configRegistry() if ($host eq '-');

	# Connect to the registry service and lookup the requested service.
	my $reg = new IO::Socket::INET(Proto => 'tcp',
			PeerAddr => "$host", PeerPort => 63000)
		or die "Conmux::connect: registry not available - $@\n";

	my %r = Conmux::sendCmd($reg, 'LOOKUP', { 'service' => $service });
	die "Conmux::Registry::lookup: $service: error - $r{'status'}\n"
		if ($r{status} ne "OK");

	close($reg);

	$r{'result'};
}

sub add {
	my ($host, $service, $location) = @_;

	$host = Conmux::configRegistry() if ($host eq '-');

	# Connect to the registry service and lookup the requested service.
	my $reg = new IO::Socket::INET(Proto => 'tcp',
			PeerAddr => "$host", PeerPort => 63000)
		or die "Conmux::connect: registry not available - $@\n";

	my %r = Conmux::sendCmd($reg, 'ADD', { 'service' => $service,
		'location' => $location });
	die "Conmux::Registry::add: $service: error - $r{'status'}\n"
		if ($r{status} ne "OK");

	close($reg);

	1;
}

sub list {
	my ($host, $service, $location) = @_;
	my (@results, %r);

	$host = Conmux::configRegistry() if ($host eq '-');

	# Connect to the registry service and ask for a list.
	my $reg = new IO::Socket::INET(Proto => 'tcp',
			PeerAddr => "$host", PeerPort => 63000)
		or die "Conmux::connect: registry not available - $@\n";

	%r = Conmux::sendCmd($reg, 'LIST', { });
##	while ($r{'status'} eq 'more') {
##		%r = receiveResult($reg);
##		push(@results, $r{'result'});
##	}
	die "Conmux::Registry::list: error - $r{'status'}\n"
		if ($r{'status'} ne "OK");

	close($reg);

	$r{'result'};
}

1;
