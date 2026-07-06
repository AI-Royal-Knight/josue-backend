#!/bin/bash
echo "Checking for date_raised..."
grep -r "date_raised" .
echo "Checking for variation_value..."
grep -r "variation_value" .
echo "Checking for material_target..."
grep -r "material_target" .
echo "Checking for claimed_amount..."
grep -r "claimed_amount" .
