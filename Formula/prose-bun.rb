class ProseBun < Formula
  desc "Run Prose programs through an installed agent harness"
  homepage "https://prose.md"
  version "0.15.0-rc.2"
  license "MIT"
  on_macos do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-bun-0.15.0-rc.2-darwin-arm64.tar.gz"
      sha256 "5ed473e21f8b6dd46412459ef8171f77c6eda451f02d940ff9581dd4053c6582"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-bun-0.15.0-rc.2-darwin-x64.tar.gz"
      sha256 "fe145e3afa5d6cfab15e7208a58543adaef9104e13c623954724dc49cd1d8f81"
    end
  end
  on_linux do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-bun-0.15.0-rc.2-linux-arm64-gnu.tar.gz"
      sha256 "a833d597fbc3f8373fb09c18e3290fe8e72e05d32b19bd736dc8948bc10e69b3"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-bun-0.15.0-rc.2-linux-x64-gnu.tar.gz"
      sha256 "6da93c5a0cd500d665c7cef5426b295881aa02e5d4f858bd7bfe1764bf7fd828"
    end
  end

  def install
    bin.install "prose" => "prose"
  end

  def caveats
    <<~EOS
      Install and authenticate a supported agent harness separately.
      Linux requires glibc 2.34 or newer.
      This is an experimental prerelease.
      macOS binaries are not Developer ID signed or notarized.
    EOS
  end

  test do
    assert_equal "prose 0.15.0-rc.2 (bun)", shell_output("#{bin}/prose --version").strip
  end
end
