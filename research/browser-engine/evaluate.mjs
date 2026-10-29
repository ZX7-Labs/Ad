/** Research fixture acceptance gates: only complete authored captures can pass. */
const rates=['12/1','30000/1001'];
const order=[0,7,3,11,7,0];

export function evaluateCapture(results) {
  const coverage_passed=Array.isArray(results) && results.length===rates.length &&
    results.every((group,i)=>
      `${group.rate?.num}/${group.rate?.den}`===rates[i] &&
      Array.isArray(group.frames) && group.frames.length===order.length &&
      group.frames.every((frame,j)=>frame.index===order[j]));
  const frames=coverage_passed?results.flatMap(group=>group.frames):[];
  const geometry_passed=coverage_passed && frames.every(frame=>frame.geometry_matches===true);
  const pixel_exact_passed=coverage_passed && frames.every(frame=>frame.pixel_bytes_match_svg===true);
  const repeated_passed=coverage_passed && results.every(group=>
    group.frames.every((frame,j)=>j<4 || frame.repeated_decoded_frame_matches===true));
  return {coverage_passed,geometry_passed,pixel_exact_passed,repeated_passed,
    accepted:coverage_passed && geometry_passed && pixel_exact_passed && repeated_passed};
}
