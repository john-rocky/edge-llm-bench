#!/usr/bin/perl
# iteration_pairs.pl <results/summary/device-runs.csv>
#
# Android litert-lm rows of the 1K text task (long-context-1024-gen256): each launch of
# litert_lm_advanced_main --num_iterations=2 writes two records that share one timestamp,
# iteration 1 (cold_run true) and iteration 2 (cold_run false, a fresh Conversation on the
# loaded engine). This pairs the two by timestamp, drops the cache-build launch (first_ever)
# and any launch without a prefill rate on both records, and prints per cell (device, arm,
# model, engine version): pairs, the median prefill of each iteration, the median and range of
# the per-pair ratio iteration 2 / iteration 1 for prefill and for decode, the prompt and
# generated token counts seen, and the cpu_capped mark. Reads only the summary CSV.
use strict; use warnings; use Text::ParseWords;
my $f = shift or die "usage: $0 device-runs.csv\n";
open my $h, '<', $f or die "$f: $!";
my $hdr = <$h>; chomp $hdr; my @c = parse_line(',', 0, $hdr); my %ix; $ix{$c[$_]} = $_ for 0..$#c;
my (%rec, %drop);
while (<$h>) {
  chomp; my @r = parse_line(',', 0, $_); next unless @r > 30;
  next unless $r[$ix{platform}] eq 'android' && $r[$ix{runtime}] =~ /^litert-lm-(cpu|gpu)$/
    && $r[$ix{task}] eq 'long-context-1024-gen256';
  my $cell = join('|', $r[$ix{device}], $r[$ix{runtime}], $r[$ix{model_id}], $r[$ix{engine_version}]);
  my $launch = "$cell|$r[$ix{timestamp}]";
  $drop{$launch} = 'first_ever' if lc($r[$ix{first_ever}]) eq 'true';
  my $it = lc($r[$ix{cold_run}]) eq 'true' ? 1 : 2;
  $rec{$launch}{$it} = { prefill => $r[$ix{prefill_tps}], decode => $r[$ix{decode_tps}],
                         prompt => $r[$ix{prompt_tokens}], gen => $r[$ix{gen_tokens}],
                         capped => $r[$ix{cpu_capped}], text => $r[$ix{text_check}] };
}
sub med { my @a = sort { $a <=> $b } @_; my $n = @a or return undef;
          return $n % 2 ? $a[$n/2] : ($a[$n/2-1] + $a[$n/2]) / 2 }
my %cell; my ($pairs, $dropped_first, $dropped_incomplete, $dropped_short) = (0, 0, 0, 0);
for my $l (sort keys %rec) {
  if ($drop{$l}) { $dropped_first++; next }
  my ($a, $b) = ($rec{$l}{1}, $rec{$l}{2});
  unless ($a && $b && $a->{prefill} ne '' && $b->{prefill} ne '' && $a->{prefill} > 0 && $b->{prefill} > 0) {
    $dropped_incomplete++; next }
  # a launch whose prompt came out under 1,000 tokens did not run the 1K task (a chat template that dropped
  # the user turn leaves 8 or 9 prompt tokens): not a pair of this table
  unless ($a->{prompt} ne '' && $b->{prompt} ne '' && $a->{prompt} >= 1000 && $b->{prompt} >= 1000) {
    $dropped_short++; next }
  my ($cellk) = $l =~ /^(.*)\|[^|]*$/; $pairs++;
  push @{$cell{$cellk}{p1}}, $a->{prefill}; push @{$cell{$cellk}{p2}}, $b->{prefill};
  push @{$cell{$cellk}{rp}}, $b->{prefill} / $a->{prefill};
  push @{$cell{$cellk}{rd}}, ($a->{decode} > 0 ? $b->{decode} / $a->{decode} : 0);
  $cell{$cellk}{prompt}{"$a->{prompt}/$b->{prompt}"}++; $cell{$cellk}{gen}{"$a->{gen}/$b->{gen}"}++;
  $cell{$cellk}{capped}{$a->{capped} eq '' ? '-' : $a->{capped}}++;
}
print "| device | arm | model | engine version | pairs | prefill it1 median | prefill it2 median | prefill it2/it1 median [min-max] | decode it2/it1 median | prompt / gen tokens | cpu_capped |\n";
print "|---|---|---|---|---:|---:|---:|---|---:|---|---|\n";
for my $k (sort keys %cell) {
  my ($d, $rt, $m, $e) = split /\|/, $k; my $c = $cell{$k}; my @rp = sort { $a <=> $b } @{$c->{rp}};
  printf "| %s | %s | %s | %s | %d | %.1f | %.1f | %.2f [%.2f-%.2f] | %.2f | %s / %s | %s |\n",
    $d, $rt, $m, $e, scalar @rp, med(@{$c->{p1}}), med(@{$c->{p2}}), med(@rp), $rp[0], $rp[-1], med(@{$c->{rd}}),
    join(';', sort keys %{$c->{prompt}}), join(';', sort keys %{$c->{gen}}), join(';', sort keys %{$c->{capped}});
}
printf "\npairs %d; launches dropped: first_ever %d, incomplete %d, prompt under 1,000 tokens %d\n",
  $pairs, $dropped_first, $dropped_incomplete, $dropped_short;
