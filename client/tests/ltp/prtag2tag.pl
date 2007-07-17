#! /usr/bin/perl
# prtag2tag.pl: print lines from input_file from /TAG1/ thru /TAG2/ (or EOF)
# (C) Copyright 2007, Randy Dunlap
#
# TBD: howto handle stdin vs. filename?
# TBD: add ignorecase option;

sub usage() {
	print "usage: prtag2tag begin_tag end_tag file(s)\n";
	exit (1);
}

my $printing = 0;
my $begin_tag = shift (@ARGV) || usage();
my $end_tag = shift (@ARGV) || usage();

if ($begin_tag eq "" || $end_tag eq "") {
	usage();
}

foreach my $file (@ARGV) {

	open (FILE, $file) || die "Cannot open file: $file\n";

	LINE: while ($line = <FILE>) {
		chomp $line;

		if ($line =~ /$begin_tag/) {
			$printing = 1;
		}

		if ($printing) {
			print "$line\n";
		}

		if ($line =~ /$end_tag/) {
			$printing = 0;
		}
	}

	close (FILE);
}
