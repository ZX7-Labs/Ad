import test from 'node:test';
import assert from 'node:assert/strict';
import {evaluateCapture} from './evaluate.mjs';

const order=[0,7,3,11,7,0];
const groups=()=>[{num:12,den:1},{num:30000,den:1001}].map(rate=>({
  rate,frames:order.map((index,i)=>({index,geometry_matches:true,pixel_bytes_match_svg:true,
    repeated_decoded_frame_matches:i>=4?true:null}))
}));

test('both complete rates and exact repeated captures qualify',()=>{
  assert.deepEqual(evaluateCapture(groups()),{
    coverage_passed:true,geometry_passed:true,pixel_exact_passed:true,
    repeated_passed:true,accepted:true
  });
});
test('a pixel mismatch fails even with correct rectangle geometry',()=>{
  const data=groups();data[1].frames[3].pixel_bytes_match_svg=false;
  const verdict=evaluateCapture(data);
  assert.equal(verdict.geometry_passed,true);
  assert.equal(verdict.pixel_exact_passed,false);
  assert.equal(verdict.accepted,false);
});
test('duplicate capture must be verified as a repeat',()=>{
  const data=groups();data[0].frames[4].repeated_decoded_frame_matches=null;
  assert.equal(evaluateCapture(data).accepted,false);
  assert.equal(evaluateCapture(data).repeated_passed,false);
});
test('incomplete/empty receipts cannot produce vacuous success',()=>{
  for(const data of [[],[groups()[0]],groups().map(g=>({...g,frames:g.frames.slice(0,5)}))]){
    assert.equal(evaluateCapture(data).coverage_passed,false);
    assert.equal(evaluateCapture(data).accepted,false);
  }
});
test('failed geometry blocks acceptance',()=>{
  const data=groups();data[0].frames[0].geometry_matches=false;
  assert.equal(evaluateCapture(data).accepted,false);
});
