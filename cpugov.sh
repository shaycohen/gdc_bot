GOV=$1
echo "cpugov $1"
[[ -z $GOV ]] && { 
	for file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo $file; cat $file; done
} || { 
	for file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo "$GOV" > $file; done
	for file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo $file; cat $file; done
}

