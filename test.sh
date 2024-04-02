#! /bin/bash
doo() {
    echo "starting"
    sleep 20
    echo "finishing"
}

doo </dev/null &>agg.log &
p=$!
echo $p

sleep 2

doo </dev/null &>agg.log &
q=$!
echo $q

echo "/proc/$p"
echo "/proc/$q"
echo "/proc/${p}"
echo "/proc/${q}"

[ -d "/proc/$p" ] && echo "p exists" || echo "p not exists"
[ -d "/proc/$q" ] && echo "q exists" || echo "q not exists"

echo "waiting p"
wait $p

echo "waiting q"
wait $q

echo "waiting all"
wait
