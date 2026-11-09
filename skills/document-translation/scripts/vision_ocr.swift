// Optional macOS local OCR. Does not infer semantic correctness.
import Foundation
import Vision
import AppKit
if CommandLine.arguments.count < 2 { fputs("Usage: swift vision_ocr.swift image [en-US,zh-Hans]\n",stderr);exit(2) }
let url=URL(fileURLWithPath:CommandLine.arguments[1])
let request=VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
// Let Vision select the supported compute device and newest installed revision.
// Forcing legacy CPU/revision-1 execution can fail on current Apple runtimes.
if let revision = VNRecognizeTextRequest.supportedRevisions.last { request.revision = revision }
if CommandLine.arguments.count>2 { request.recognitionLanguages=CommandLine.arguments[2].split(separator:",").map(String.init) }
do {
 let handler=VNImageRequestHandler(url:url,options:[:]);try handler.perform([request])
 let results=(request.results ?? []).compactMap { o -> [String:Any]? in
  guard let c=o.topCandidates(1).first else{return nil}
  return ["text":c.string,"confidence":c.confidence,"bbox":[o.boundingBox.minX,o.boundingBox.minY,o.boundingBox.width,o.boundingBox.height],"bbox_units":"normalized bottom-left"]
 }
 let data=try JSONSerialization.data(withJSONObject:results,options:[.prettyPrinted,.sortedKeys]);print(String(data:data,encoding:.utf8)!)
} catch { fputs("OCR error: \(error)\n",stderr);exit(1) }
