#!/usr/bin/perl
# cap_table.pl <cap_timeline2.out>  -> markdown table of the committed launches (phone, model, version, launch, prefill
# it1 -> it2, the CPU clock ceiling at the start of each iteration's prefill and the lowest during it, MHz per policy).
use strict; use warnings;
my %untracked;
my @rows;
while (<>) {
  chomp; next if /skipped/;
  my ($dir, $model, $date, $time) = /^results\/raw\/(\S+) : (\S+) (\d{4}-\d\d-\d\d) (\d\d:\d\d)/ or next;
  $dir =~ s/-android$//; next if $untracked{$dir};
  my $phone = $dir =~ /s26/ ? 'Galaxy S26' : 'Pixel 8a';
  my $ver = $date ge '2026-10-14' ? 'v0.18.0' : 'v0.16.0';
  my ($p1, $p2, $r) = /prefill (\d+) -> (\d+) tok\/s \(x([\d.]+)\)/;
  my @w;
  for my $i (1, 2) {
    if (/it$i prefill ([\d.]+)-([\d.]+)s: ceiling at start (\S+) MHz, lowest in it ([^;\s]+)/) { push @w, [$3, ($4 =~ s/;$//r), sprintf('%.0f-%.0f s', $1, $2)] }
    else { push @w, ['?', '?', 'unknown'] }
  }
  my $samples = /events: \S/ ? '' : ' (no ceiling samples)';
  $model =~ s/-it-litert-lm//; $model =~ s/_dynamic_wi4b32_afp32_r0805meta018/ (dynamic int4)/;
  push @rows, [$phone, $model, $ver, "$date $time", $p1, $p2, $r, @{$w[0]}[0,1], @{$w[1]}[0,1], $w[1][2], $samples];
}
print "| phone | model | engine | launch (UTC) | prefill it1 | prefill it2 | it2 / it1 | ceiling at it1 prefill start | lowest in it1 prefill | ceiling at it2 prefill start | lowest in it2 prefill | it2 prefill window |\n";
print "|---|---|---|---|---:|---:|---:|---|---|---|---|---|\n";
for my $r (sort { $a->[0] cmp $b->[0] || $a->[1] cmp $b->[1] || $a->[3] cmp $b->[3] } @rows) {
  my $note = pop @$r; $r->[11] .= $note;
  print '| ', join(' | ', @$r), " |\n";
}
printf "\nlaunches %d (committed campaigns only; MHz per cpufreq policy, little to big cores: Galaxy S26 policy0 = cpu0-5 max 3628, policy6 = cpu6-7 max 4742; Pixel 8a policy0 = cpu0-3 max 1704, policy4 = cpu4-7 max 2367, policy8 = cpu8 max 2914)\n", scalar @rows;
