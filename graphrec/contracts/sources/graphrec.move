/// Định nghĩa Token GREC ở một module riêng biệt.
module graphrec::grec {
    use std::option;
    use sui::coin;

    /// OTW cho token GREC
    public struct GREC has drop {}

    #[allow(deprecated_usage)]
    fun init(otw: GREC, ctx: &mut sui::tx_context::TxContext) {
        let (treasury_cap, metadata) = coin::create_currency(
            otw,
            6,                              
            b"GREC",                        
            b"GraphRec Token",              
            b"Loyalty token cho he thong de xuat san pham GraphRec",
            option::none(),
            ctx,
        );

        sui::transfer::public_freeze_object(metadata);
        sui::transfer::public_transfer(treasury_cap, sui::tx_context::sender(ctx));
    }
}

/// Module: graphrec
/// GraphRec Loyalty & NFT System trên SUI blockchain.
module graphrec::graphrec {
    use std::string::{Self, String};
    use std::vector;
    use sui::coin::{Self, TreasuryCap};
    use sui::balance::{Self, Balance};
    use sui::table::{Self, Table};
    use sui::object::{Self, ID, UID};
    use sui::event;
    use sui::clock::{Self, Clock};
    use sui::url::{Self, Url};
    use sui::display;
    use sui::package;
    
    // Import token từ module grec ở trên
    use graphrec::grec::GREC;

    // ── Error codes ────────────────────────────────────────────────────────────
    const EInsufficientBalance: u64 = 0;

    // ── Reward amounts (in GREC units, 1 GREC = 1_000_000 MIST equivalent) ───
    const REWARD_VIEWED:   u64 = 10_000_000;  // 10 GREC  — khi xem sản phẩm
    const REWARD_BOUGHT:   u64 = 100_000_000; // 100 GREC — khi mua sản phẩm
    const REWARD_REVIEWED: u64 = 50_000_000;  // 50 GREC  — khi đánh giá

    // ── One-Time Witness cho Module này (Dùng cho NFT Display) ─────────────────
    public struct GRAPHREC has drop {}

    // ── Core objects ──────────────────────────────────────────────────────────

    /// RewardPool — Quản lý kho token thưởng GREC
    public struct RewardPool has key {
        id:         UID,
        balance:    Balance<GREC>,
        admin:      address,
        total_distributed: u64,
        tx_count:   u64,
    }

    public struct AdminCap has key, store {
        id: UID,
    }

    public struct ProductNFT has key, store {
        id:           UID,
        product_id:   String,
        name:         String,
        description:  String,
        image_url:    Url,
        brand:        String,
        category:     String,
        price_grec:   u64,
        rating:       u8,
        minted_at:    u64,
        serial:       u64,
    }

    public struct RecommendScore has key, store {
        id:          UID,
        owner:       address,
        top_products: vector<String>,
        scores:       vector<u64>,
        updated_at:   u64,
        version:      u64,
    }

    public struct UserProfile has key, store {
        id:           UID,
        user_id:      String,
        wallet:       address,
        viewed_count: u64,
        bought_count: u64,
        review_count: u64,
        total_earned: u64,
        joined_at:    u64,
    }

    public struct Registry has key {
        id:           UID,
        user_map:     Table<address, ID>,
        total_users:  u64,
        total_nfts:   u64,
        nft_serial:   u64,
    }

    // ── Events ────────────────────────────────────────────────────────────────

    public struct TokenRewarded has copy, drop {
        recipient:   address,
        amount:      u64,
        reason:      String,    
        product_id:  String,
        timestamp:   u64,
    }

    public struct NFTMinted has copy, drop {
        owner:       address,
        nft_id:      ID,
        product_id:  String,
        serial:      u64,
        timestamp:   u64,
    }

    public struct ScoreUpdated has copy, drop {
        owner:       address,
        version:     u64,
        top_product: String,   
        top_score:   u64,
        timestamp:   u64,
    }

    public struct UserRegistered has copy, drop {
        wallet:    address,
        user_id:   String,
        timestamp: u64,
    }

    // ── Init ──────────────────────────────────────────────────────────────────

    fun init(otw: GRAPHREC, ctx: &mut sui::tx_context::TxContext) {
        let admin_cap = AdminCap { id: object::new(ctx) };
        let admin_addr = sui::tx_context::sender(ctx);

        let pool = RewardPool {
            id:               object::new(ctx),
            balance:          balance::zero<GREC>(),
            admin:            admin_addr,
            total_distributed: 0,
            tx_count:          0,
        };
        sui::transfer::share_object(pool);

        let registry = Registry {
            id:          object::new(ctx),
            user_map:    table::new(ctx),
            total_users: 0,
            total_nfts:  0,
            nft_serial:  0,
        };
        sui::transfer::share_object(registry);

        // Thiết lập Display NFT bằng OTW của module này
        let publisher = package::claim(otw, ctx);
        let mut display = display::new<ProductNFT>(&publisher, ctx);
        
        display::add(&mut display, string::utf8(b"name"),        string::utf8(b"{name}"));
        display::add(&mut display, string::utf8(b"description"), string::utf8(b"{description}"));
        display::add(&mut display, string::utf8(b"image_url"),   string::utf8(b"{image_url}"));
        display::add(&mut display, string::utf8(b"brand"),       string::utf8(b"{brand}"));
        display::add(&mut display, string::utf8(b"category"),    string::utf8(b"{category}"));
        display::add(&mut display, string::utf8(b"project_url"), string::utf8(b"https://graphrec.demo"));
        
        display::update_version(&mut display);
        sui::transfer::public_transfer(display, admin_addr);
        sui::transfer::public_transfer(publisher, admin_addr);
        sui::transfer::public_transfer(admin_cap, admin_addr);
    }

    // ── Admin functions ───────────────────────────────────────────────────────

    public fun fund_pool(
        _cap:     &AdminCap,
        treasury: &mut TreasuryCap<GREC>,
        pool:     &mut RewardPool,
        amount:   u64,
        _ctx:     &mut sui::tx_context::TxContext,
    ) {
        let minted = coin::mint_balance(treasury, amount);
        balance::join(&mut pool.balance, minted);
    }

    // ── User functions ────────────────────────────────────────────────────────

    #[allow(lint(self_transfer))]
    public fun register_user(
        registry: &mut Registry,
        user_id:  vector<u8>,
        clock:    &Clock,
        ctx:      &mut sui::tx_context::TxContext,
    ) {
        let sender = sui::tx_context::sender(ctx);
        let ts = clock::timestamp_ms(clock);

        let profile = UserProfile {
            id:           object::new(ctx),
            user_id:      string::utf8(user_id),
            wallet:       sender,
            viewed_count: 0,
            bought_count: 0,
            review_count: 0,
            total_earned: 0,
            joined_at:    ts,
        };
        let profile_id = object::id(&profile);
        
        if (!table::contains(&registry.user_map, sender)) {
            table::add(&mut registry.user_map, sender, profile_id);
            registry.total_users = registry.total_users + 1;
        };

        sui::transfer::public_transfer(profile, sender);

        event::emit(UserRegistered {
            wallet:    sender,
            user_id:   string::utf8(user_id),
            timestamp: ts,
        });
    }

    public fun reward_user(
        _cap:       &AdminCap,
        pool:       &mut RewardPool,
        profile:    &mut UserProfile,
        recipient:  address,
        product_id: vector<u8>,
        action:     vector<u8>,   
        clock:      &Clock,
        ctx:        &mut sui::tx_context::TxContext,
    ) {
        let action_str = string::utf8(action);
        let pid_str    = string::utf8(product_id);
        let ts         = clock::timestamp_ms(clock);
        
        let amount = if (action_str == string::utf8(b"BOUGHT")) {
            profile.bought_count = profile.bought_count + 1;
            REWARD_BOUGHT
        } else if (action_str == string::utf8(b"REVIEWED")) {
            profile.review_count = profile.review_count + 1;
            REWARD_REVIEWED
        } else {
            profile.viewed_count = profile.viewed_count + 1;
            REWARD_VIEWED
        };

        assert!(balance::value(&pool.balance) >= amount, EInsufficientBalance);
        
        let reward_balance = balance::split(&mut pool.balance, amount);
        let reward_coin    = coin::from_balance(reward_balance, ctx);
        
        sui::transfer::public_transfer(reward_coin, recipient);
        
        profile.total_earned       = profile.total_earned + amount;
        pool.total_distributed     = pool.total_distributed + amount;
        pool.tx_count              = pool.tx_count + 1;
        
        event::emit(TokenRewarded {
            recipient,
            amount,
            reason:     action_str,
            product_id: pid_str,
            timestamp:  ts,
        });
    }

    public fun mint_product_nft(
        _cap:        &AdminCap,
        registry:    &mut Registry,
        recipient:   address,
        product_id:  vector<u8>,
        name:        vector<u8>,
        description: vector<u8>,
        image_url:   vector<u8>,
        brand:       vector<u8>,
        category:    vector<u8>,
        price_grec:  u64,
        rating:      u8,
        clock:       &Clock,
        ctx:         &mut sui::tx_context::TxContext,
    ) {
        registry.nft_serial = registry.nft_serial + 1;
        registry.total_nfts = registry.total_nfts + 1;
        
        let serial = registry.nft_serial;
        let ts     = clock::timestamp_ms(clock);
        
        let nft = ProductNFT {
            id:          object::new(ctx),
            product_id:  string::utf8(product_id),
            name:        string::utf8(name),
            description: string::utf8(description),
            image_url:   url::new_unsafe_from_bytes(image_url),
            brand:       string::utf8(brand),
            category:    string::utf8(category),
            price_grec,
            rating,
            minted_at:   ts,
            serial,
        };
        
        let nft_id = object::id(&nft);
        sui::transfer::public_transfer(nft, recipient);

        event::emit(NFTMinted {
            owner:      recipient,
            nft_id,
            product_id: string::utf8(product_id),
            serial,
            timestamp:  ts,
        });
    }

    public fun update_recommend_score(
        _cap:         &AdminCap,
        owner:        address,
        top_products: vector<vector<u8>>,
        scores:       vector<u64>,
        clock:        &Clock,
        ctx:          &mut sui::tx_context::TxContext,
    ) {
        let ts         = clock::timestamp_ms(clock);
        let mut pid_strs   = vector::empty<String>();
        let mut i      = 0;
        
        let top_score  = if (!vector::is_empty(&scores)) { *vector::borrow(&scores, 0) } else { 0 };
        let top_pid    = if (!vector::is_empty(&top_products)) {
            string::utf8(*vector::borrow(&top_products, 0))
        } else {
            string::utf8(b"")
        };
        
        while (i < vector::length(&top_products)) {
            vector::push_back(&mut pid_strs, string::utf8(*vector::borrow(&top_products, i)));
            i = i + 1;
        };

        let score_obj = RecommendScore {
            id:           object::new(ctx),
            owner,
            top_products: pid_strs,
            scores,
            updated_at:   ts,
            version:      1,
        };

        sui::transfer::public_transfer(score_obj, owner);
        
        event::emit(ScoreUpdated {
            owner,
            version:     1,
            top_product: top_pid,
            top_score,
            timestamp:   ts,
        });
    }

    // ── View functions ────────────────────────────────────────────────────────

    public fun pool_balance(pool: &RewardPool): u64 {
        balance::value(&pool.balance)
    }

    public fun pool_stats(pool: &RewardPool): (u64, u64, u64) {
        (
            balance::value(&pool.balance),
            pool.total_distributed,
            pool.tx_count,
        )
    }

    public fun nft_product_id(nft: &ProductNFT): String { nft.product_id }
    public fun nft_serial(nft: &ProductNFT): u64 { nft.serial }
    
    public fun registry_stats(r: &Registry): (u64, u64) {
        (r.total_users, r.total_nfts)
    }
}
