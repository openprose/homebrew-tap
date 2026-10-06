class ProseRust < Formula
  desc "Run Prose programs through an installed agent harness"
  homepage "https://prose.md"
  version "0.15.0-rc.3"
  license "MIT"
  on_macos do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-rust-0.15.0-rc.3-darwin-arm64.tar.gz"
      sha256 "7fb6507a730bdc8f0559787033359b20fc61b90d62778a53fefc31691276b152"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-rust-0.15.0-rc.3-darwin-x64.tar.gz"
      sha256 "ad1bc60edc609bd1bcb78d7cbeddc132263467f9833d18d00ce8f86ac734a0fa"
    end
  end
  on_linux do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-rust-0.15.0-rc.3-linux-arm64-gnu.tar.gz"
      sha256 "2a79fdc3014c06308b9833f5fba3be170379d460fb3d4da5b3f1dce60d5546d3"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-rust-0.15.0-rc.3-linux-x64-gnu.tar.gz"
      sha256 "804bbd4d93ba975d80a1ca3c96313de65ca4b404177ab2a671d8d2ccf3b291e7"
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
    assert_equal "prose 0.15.0-rc.3 (rust)", shell_output("#{bin}/prose --version").strip
  end
end
