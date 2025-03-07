#!/bin/bash

# Script to set a couple of variables that depend on ALIEN_PROC_ID.
# Since several scripts might need this, it is in a separate script.

# let's get the last 10 (for INT) and 5 (for int16) digits of ALIEN_PROC_ID, to be passed to define NUMAID and shm-segment-id via O2JOBID, which are int and int16 respectively. Then we make them an int or int16
ALIEN_PROC_ID_MAX_NDIGITS_INT32=10
ALIEN_PROC_ID_MAX_NDIGITS_INT16=9
ALIEN_PROC_ID_LENTGH=`echo $ALIEN_PROC_ID | wc -l`
ALIEN_PROC_ID_OFFSET_INT32=$((ALIEN_PROC_ID_LENTGH - ALIEN_PROC_ID_MAX_NDIGITS_INT32))
ALIEN_PROC_ID_OFFSET_INT16=$((ALIEN_PROC_ID_LENTGH - ALIEN_PROC_ID_MAX_NDIGITS_INT16))
# lets's take the last 10 (int) or 5 (int16) digits
ALIEN_PROC_ID_OFFSET_INT32=${ALIEN_PROC_ID:$((ALIEN_PROC_ID_OFFSET_INT32))}
ALIEN_PROC_ID_OFFSET_INT16=${ALIEN_PROC_ID:$((ALIEN_PROC_ID_OFFSET_INT16))}
# let's make them int32 or int16, but not with the max possible value (which would be 0x7fffffff and 0x7fff respectively)
# but a bit less, to allow to add [0, 15] on top afterwards if needed (e.g. we usually add
# the NUMAID), see https://github.com/AliceO2Group/O2DPG/pull/993#pullrequestreview-1393401475
export O2JOBID=$((ALIEN_PROC_ID_OFFSET_INT32 & 0x7ffffff0))
export O2JOBSHMID=$((ALIEN_PROC_ID_OFFSET_INT16 & 0x7ff0))
echo "ALIEN_PROC_ID = $ALIEN_PROC_ID, we will set O2JOBID = $O2JOBID, SHMEMID = $SHMEMID"
