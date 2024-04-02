doo() {
    echo "starting"
    sleep 9
    echo "finishing"
}

doo </dev/null &>agg.log &
p=$!
echo $p

sleep 2

doo </dev/null &>agg.log &
echo $q
q=$!

if ! [ -z "$p" ]; then
    echo "p is not running"
fi

if ! [ -z "$q" ]; then
    echo "q is not running"
fi

echo "waiting p"
wait $p

echo "waiting q"
wait $q
