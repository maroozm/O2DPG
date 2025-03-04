#include <string>
#include <vector>
#include <filesystem>

// overlay 1D histograms
void overlay1D(std::vector<TH1*> hVec, std::vector<std::string> labelVec, TLegend* legend, std::string const& outputDir)
{
  TCanvas c("overlay", "", 800, 800);
  c.cd();


  TPad lower_pad("lower_pad","lower_pad",0,0.05,1.,0.3);
  TPad upper_pad("upper_pad","upper_pad",0,0.25,1.,1.);
  upper_pad.Draw();
  lower_pad.Draw();

  const int colors[6]={kRed,kBlue,kGreen,kMagenta,kCyan,kOrange}; //TODO what if more then 6 histograms
  const int linestyles[6]={1,10,2,9,8,7}; //TODO what if more then 6 histograms

  TLegend legendOverlay(0.65, 0.8, 0.9, 0.9);
  legendOverlay.SetFillStyle(0);
  int counter = 0;
  for (auto h : hVec){
    upper_pad.cd();
    h->SetStats(0);
    h->SetLineStyle(linestyles[counter]);
    h->SetLineWidth(1);
    h->SetLineColor(colors[counter]);
    TH1F* hClone = (TH1F*)h->Clone();

    h->GetXaxis()->SetLabelSize(0.);
    h->GetXaxis()->SetLabelOffset(999);
    h->GetYaxis()->SetLabelSize(0.05);

    legendOverlay.AddEntry(h, labelVec[counter].c_str());

    h->Draw("same E hist");

    lower_pad.cd();
    hClone->Divide(h,hVec[0],1.0,1.0,"B"); // error option?
    hClone->SetTitle("");
    hClone->SetLineStyle(1);
    hClone->GetYaxis()->SetRangeUser(0.,10.);
    hClone->GetYaxis()->SetLabelSize(0.125);
    hClone->GetXaxis()->SetLabelSize(0.125);
    if (counter>0){
      hClone->Draw("same E1");
    }
    else {
      hClone->Draw("same");
    }
    counter++;
  }
  upper_pad.cd();
  if (legend){
    legend->Draw("same");
  }
  legendOverlay.Draw("same");

  auto savePath = outputDir + "/" + hVec[0]->GetName() + ".png";
  c.SaveAs(savePath.c_str());
  c.Close();
}

// overlay 2D histograms
void overlay2D(std::vector<TH1*> hVec1, std::vector<std::string> labelVec, TLegend* legend, std::string const& outputDir)
{
  std::vector<TH2*> hVec;
  for (auto h : hVec1){
    hVec.push_back(dynamic_cast<TH2*>(h));
  }
  int nHistos = hVec.size();

  TCanvas c("overlay", "", 2400, 800*(nHistos-1));
  c.Divide(3, nHistos-1);
  c.cd(1);
  hVec[0]->SetTitle(hVec[0]->GetTitle() + TString("(" + labelVec[0] + ")"));
  hVec[0]->SetStats(0);
  hVec[0]->Draw("colz");

  for (int i = 1; i<nHistos; i++){
    auto hDiv = (TH2*)hVec[i]->Clone(Form("%s_ratio", hVec[i]->GetName()));
    hDiv->SetTitle(hVec[i]->GetTitle() + TString("(" + labelVec[i] + "/"+labelVec[0]+")"));
    hDiv->SetStats(0);
    hDiv->Divide(hVec[0]);
    hVec[i]->SetTitle(hVec[i]->GetTitle() + TString("(" + labelVec[i] + ")"));
    hVec[i]->SetStats(0);

    c.cd(i*3-1);
    hVec[i]->Draw("colz");

    c.cd(i*3);
    hDiv->Draw("colz");
  }

  if (legend){
    c.cd(3);
    legend->Draw();
  }

  auto savePath = outputDir + "/" + hVec[0]->GetName() + ".png";
  c.SaveAs(savePath.c_str());
  c.Close();
}

// entry point for overlay plots from ReleaseValidation.C
void PlotOverlayAndRatio(std::vector<TH1*> hVec, std::vector<std::string> labelVec, std::string outputDir = "overlayPlots", TLegend* legendMetrics = nullptr)
{
  if (!std::filesystem::exists(outputDir)) {
    std::filesystem::create_directory(outputDir);
  }

  bool is2D = false;
  for (auto h : hVec){
  	if (dynamic_cast<TH3*>(h)){
  		 std::cerr << "Cannot yet overlay 3D histograms\nSkipping " << h->GetName() << "\n";
    return;
  	}
    if (dynamic_cast<TH2*>(h)){
    is2D = true;
    }
  }

  if (is2D){
    overlay2D(hVec, labelVec, legendMetrics, outputDir);
  }
  else {
    overlay1D(hVec, labelVec, legendMetrics, outputDir);
  }
}

// entry point for plotting only overlays
void PlotOverlays(initializer_list<std::string> fileNames_list, initializer_list<std::string> labelVec_list, std::string outputDir = "overlayPlots"){
  std::vector<std::string> fileNames(fileNames_list);
  std::vector<std::string> labelVec(labelVec_list);

  if (fileNames.size() > labelVec.size()){
    for (int i=labelVec.size();i<fileNames.size(); i++){
      labelVec.push_back("File"+std::to_string(i+1));
    }
  }

  std::vector<TFile*> files;
  for (auto& fileName : fileNames){
    TFile* thisFile = TFile::Open(fileName.c_str(), "READ");
    files.push_back(thisFile);
  }

  TIter next(files[0]->GetListOfKeys());
  TKey* key{};
  while ((key = static_cast<TKey*>(next()))) {
    std::vector<TH1*> hVec;
    hVec.push_back(static_cast<TH1*>(key->ReadObj()));
    auto oname = key->GetName();
    bool foundAll = true;
    for (int i=1; i<files.size();i++){
      auto hNew = static_cast<TH1*>(files[i]->Get(oname));
      if (!hNew) {
        // That could still happen in case we compare either comletely different file by accident or something has been changed/added/removed
        foundAll = false;
        std::cerr << "ERROR: Histogram " << oname << " not found in file " << fileNames[i].c_str() << "\n";
      }
      hVec.push_back(hNew);
    }
    if (foundAll){
      PlotOverlayAndRatio(hVec, labelVec, outputDir);
    }
    else {
      std::cerr << "ERROR: Histogram " << oname << " not found in all files\n";
      return;
    }
  }
}
