#!/usr/bin/perl
# cap_timeline2.pl <run.log> ...
# Per stored launch: the CPU clock ceiling (sampler CPUMAX lines, printed when a value changes, 0.5 s ticks placed at
# t0 + 1 + k * period) against the engine's own iteration timeline (absl timestamps of the two BenchmarkInfo prints,
# prefill / decode durations). Prints the ceiling at the start of each iteration's prefill and the lowest ceiling
# during each prefill, in MHz per policy, plus the event list.
use strict; use warnings;
sub mhz { my $s = shift; my $star = $s =~ s/\*$// ? "*" : ""; join("/", map { $_ eq "-" ? "-" : sprintf("%d", $_ / 1000) } split " ", $s) . $star }
for my $f (@ARGV) {
  open my $h, '<', $f or do { warn "$f: $!"; next }; local $/; my $t = <$h>; close $h;
  my ($pre, $post) = split /===ENGINE_OUTPUT===\n/, $t, 2; $post //= '';
  my ($ticks, @ev) = (0);
  for my $l (split /\n/, $pre) { if ($l =~ /^VmRSS:/) { $ticks++ } elsif ($l =~ /^CPUMAX (.*)$/) { push @ev, [$ticks, $1] } }
  my (@stamps, @pre_d, @dec_d, @pre_s, @dec_s, @bench_t, $t0, $last);
  for my $l (split /\n/, $post) {
    if ($l =~ /^[IWEF]\d{4} \d\d:\d\d:(\d+\.\d+)/) { my $s = $1; $t0 //= $s; push @stamps, $s; $last = $s }
    if ($l =~ /^(?:[IWEF]\d{4} .*?)?\s*BenchmarkInfo:\s*$/ && defined $last) { push @bench_t, $last }
    elsif ($l =~ /Prefill Turn 1: Processed (\d+) tokens in (?:(\d+)m)?([\d.]+)s/) { push @pre_d, ($2 // 0) * 60 + $3 }
    elsif ($l =~ /Decode Turn 1: Processed (\d+) tokens in (?:(\d+)m)?([\d.]+)s/) { push @dec_d, ($2 // 0) * 60 + $3 }
    elsif ($l =~ /Prefill Speed: ([\d.]+) tokens\/sec/) { push @pre_s, $1 }
    elsif ($l =~ /Decode Speed: ([\d.]+) tokens\/sec/) { push @dec_s, $1 }
  }
  (my $name = $f) =~ s{.*/results/raw/}{}; $name =~ s{-android/app-path-android/litert-lm-cpu_litert-community_}{ : }; $name =~ s/_long-context.*?_(\d{4}-\d\d-\d\d)T(\d\d)-(\d\d)-\d\d.*/ $1 $2:$3/;
  unless (defined $t0 && @bench_t >= 2 && @pre_d >= 2) { printf "%s: skipped (bench %d, prefill %d)\n", $name, scalar @bench_t, scalar @pre_d; next }
  my $tend = $stamps[-1]; my $life = $tend - $t0; my $period = $ticks > 0 ? ($life - 1) / $ticks : 0;
  my @win;   # [prefill start, prefill end] per iteration, relative to t0; decode duration from the Decode Turn line,
             # else from the gen tokens / decode speed is unknown -> use the BenchmarkInfo time minus the prefill only (marked ~)
  my @mark;
  for my $i (0, 1) {
    my $end = $bench_t[$i] - $t0;
    if (defined $dec_d[$i]) { my $ds = $end - $dec_d[$i]; push @win, [$ds - $pre_d[$i], $ds]; push @mark, '' }
    else { push @win, [undef, undef]; push @mark, '?' }
  }
  # the prefill of iteration 1 starts after init; when its decode duration is unknown, place it from the next known point
  my @evt = map { [1 + $_->[0] * $period, $_->[1]] } @ev;
  my $ceil_at = sub { my $x = shift; my $v = "-"; for (@evt) { $v = $_->[1] if $_->[0] <= $x } $v = $evt[0][1] . "*" if $v eq "-" && @evt; return $v };
  my $min_in = sub { my ($a, $b) = @_; my @vals = ($ceil_at->($a)); $vals[0] =~ s/\*$//; push @vals, $_->[1] for grep { $_->[0] > $a && $_->[0] <= $b } @evt;
    my @cols; for my $v (@vals) { my @p = split ' ', $v; for my $j (0..$#p) { $cols[$j] = $p[$j] if $p[$j] ne "-" && (!defined $cols[$j] || $cols[$j] eq "-" || $p[$j] < $cols[$j]); $cols[$j] //= "-" } } return join(' ', map { $_ // '-' } @cols) };
  my @out;
  for my $i (0, 1) {
    if (defined $win[$i][0]) { push @out, sprintf("it%d prefill %.1f-%.1fs: ceiling at start %s MHz, lowest in it %s", $i + 1, @{$win[$i]}, mhz($ceil_at->($win[$i][0])), mhz($min_in->(@{$win[$i]}))) }
    else { push @out, sprintf("it%d prefill window unknown (no decode line), BenchmarkInfo at %.1fs", $i + 1, $bench_t[$i] - $t0) }
  }
  printf "%s | prefill %.0f -> %.0f tok/s (x%.2f)%s | %s | events: %s | ticks %d, %.2fs each\n", $name, $pre_s[0], $pre_s[1], $pre_s[1] / $pre_s[0],
    (@dec_s >= 2 ? sprintf(", decode %.1f -> %.1f", $dec_s[0], $dec_s[1]) : ''), join('; ', @out),
    join(', ', map { sprintf("%.1fs %s", $_->[0], mhz($_->[1])) } @evt), $ticks, $period;
}
