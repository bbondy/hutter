// GPL-3.0-only. Read-only driver around the pinned upstream order pipeline.
// Generates the exact upstream reordered stream and an auditable page-ID index.
#include <cstdint>
#include <cstring>
#include <unistd.h>
#include <string>
#include <vector>
#include <algorithm>
#include "readalike_prepr/article_reorder.h"
#include "readalike_prepr/phda9_preprocess.h"
#include "readalike_prepr/misc.h"

int main(int argc, char** argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: prepare-order enwik9 order.tsv (fresh cwd with .new_article_order)\n");
    return 2;
  }
  if (access(argv[1], R_OK) || access(".new_article_order", R_OK)) return 2;
  if (!census_file(argv[1], ".census_prepr", 1)) return 1;
  split4Comp(".census_prepr");
  if (!cmtidx_inplace(".main", ".cmtidx_main", 1)) return 1;

  // Record the exact upstream classes, including residual corrections,
  // excluded non-redirect pages, and calendar pages.
  ord::Residual residual;
  if (!ord::ParseResidualV3(".new_article_order", &residual)) return 1;
  std::unordered_map<int32_t, uint8_t> corrected(residual.corr.begin(), residual.corr.end());
  std::unordered_map<int, int> classes;
  std::ifstream original(".main");
  std::string line;
  ord::Extractor extractor;
  ord::PageScan page;
  int unit = 0, id = -1;
  while (std::getline(original, line)) {
    if (line.compare(0, 8, "    <id>") == 0) id = std::stoi(line.substr(8));
    if (!extractor.Line(line, &page)) continue;
    int kind = 8;  // redirect
    if (!page.is_redirect) {
      auto it = corrected.find(unit);
      kind = it == corrected.end() ? page.klass : it->second;
      if (std::binary_search(residual.excl.begin(), residual.excl.end(), unit)) kind = 6;
      if (kind == 0 && page.kal >= 0) kind = 7;
      ++unit;
    }
    if (id < 0 || !classes.emplace(id, kind).second) return 1;
  }
  if (classes.size() != 243425) return 1;
  reorder();
  std::ifstream ordered(".main_reordered");
  std::ofstream index(argv[2]);
  if (!ordered || !index) return 1;
  size_t rank = 0;
  while (std::getline(ordered, line)) {
    if (line.compare(0, 8, "    <id>") != 0) continue;
    id = std::stoi(line.substr(8));
    auto found = classes.find(id);
    if (found == classes.end()) return 1;
    index << rank++ << '\t' << id << '\t' << found->second << '\n';
    classes.erase(found);
  }
  if (rank != 243425 || !classes.empty() || !index) return 1;
  fprintf(stderr, "Indexed %zu pages in exact upstream order\n", rank);
  return 0;
}
