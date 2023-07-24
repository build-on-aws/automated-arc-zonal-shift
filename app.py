#!/usr/bin/env python3

import aws_cdk as cdk

from arc_zonal_shift.zonal_shift_stack import ZonalShiftAppStack


app = cdk.App()
ZonalShiftAppStack(app, "ZonalShiftAppStack",)

app.synth()
