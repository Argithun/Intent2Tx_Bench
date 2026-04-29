#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

# 定义以太坊常用的合约地址簿
# 包含：原生代币占位符、稳定币、常用 DEX、借贷协议等
ADDRESS_BOOK_DATA = {
    "Tokens": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eb48",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "PYUSD": "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8",
        "LINK": "0x514910771af9ca656af840dff83e8264ecf986ca",
        "UNI": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
        "fwWETH": "0xa250cc729bb3323e7933022a67b52200fe354767",
        "SPX": "0xe0f63a424a4439cbe457d80e4f4b51ad25b2c56c",
        "PAXG": "0x45804880de22913dafe09f4980848ece6ecbaf78",
        "AAVE": "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9",
        "ENA": "0x57e114b691db790c35207b2e685d4a43181e6061",
        "XAUt": "0x68749665ff8d2d112fa859aa293f07a622782f38",
        "CRV": "0xd533a949740bb3306d119cc777fa900ba034cd52",
        "USDS": "0xdc035d45d973e3ec169d2276ddab16f1e407384f"
    },
    "DEX / Routers": {
        "Uniswap_V2_Router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "Uniswap_V3_Router_2": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "Universal_Router": "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad",
        "SushiSwap_Router": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        "1inch_Aggregation_Router_V5": "0x1111111254EEB25477B68fb85Ed929f73A960582",
        "1inch_Aggregation_Router_V6": "0x111111125421cA6dc452d289314280a0f8842A65",
        "0x_Protocol_V4": "0xDef1C0ded9bec7F1a1670819833240f027b25EfF",
        "Curve_Router": "0x99a58482BD75cbab83b27EC03CA68fF489b5788f",
        "Balancer_V2_Vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        "Kyberswap_V2": "0x6131B5fae19EA4f9D964eAc0408E4408b66337b5"
    },
    "Lending / Staking": {
        "Aave_V2_Lending_Pool": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "Aave_V3_Lending_Pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        "Lido_stETH": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
        "Rocket_Pool_RETH": "0xae78736Cd615f374D3085123A210448E74Fc6393",
        "Spark_V1_Lending_Pool": "0xC13e21B648A5Ee794902342038FF3aDAB66BE987",
        "Morpho_Blue_V2": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
        "Compound_V2": "0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B",
        "Compound_V3_USDC_Market": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
        "Compound_V3_WETH_Market": "0xA17581A9E3356d9A858b789D68B4d866e593aE94"
    },
    "NFT": {
        "Opensea_Seaport": "0x00000000000000ADc04C56Bf30aC9d3c0aAF14dC",
        "Blur_Blend": "0x29469395eAf6f95920E59F858042f0e28D98a20B",
        "CryptoPunks": "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB"
    },
    "Bridges / Infrastructure": {
        "Across_Spoke_Pool": "0x5c7BC2d53d245f5021E17E266bb792010103510c",
        "Optimism_L1_Standard_Bridge": "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1",
        "Arbitrum_L1_Standard_Bridge": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",
        "Base_L1_Standard_Bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
        "Polygon_RootChainManager": "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
        "Stargate_Route": "0x8731d54E9D02c286767d56ac03e8037C07e01e98",
        "Hop_Ethereum_Bridge": "0xb8901acB165ed027E32754E0FFe830802919727f",
        "Synapse_Bridge": "0x2796317b0fF8538F253012862c06787Adfb8cEb6",
        "Celer_cBridge_V2": "0x5427FEFA711Eff984124bFBB1AB6fbf5E3DA1820",
        "zkSync_Era_L1_DiamondProxy": "0x32400084C286CF3E17e7B677ea9583e60a000324"
    }
}

OUT_FILE = Path("benchmark/helpful_address_book.md")

def generate_markdown():
    # 确保目录存在
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    content = "You may refer to the following address book for commonly used Ethereum protocol addresses. This can help you avoid mistakes when inputting contract addresses for popular tokens and protocols.\n\n"
    content += "## Additional Information: Helpful Ethereum Address Book\n\n"
    content += "This address book provides a mapping between common protocol names (just a description, not contract name), token symbols, and their on-chain addresses.\n\n"
    
    for category, items in ADDRESS_BOOK_DATA.items():
        content += f"### {category}\n"
        content += "| Name / Symbol | Contract Address |\n"
        content += "| :--- | :--- |\n"
        for name, addr in items.items():
            content += f"| **{name}** | `{addr}` |\n"
        content += "\n"
    
    # 写入文件
    with OUT_FILE.open("w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"[OK] Address book generated at: {OUT_FILE}")

if __name__ == "__main__":
    generate_markdown()