window.V9_RIG={
  "status": "in_progress_small_pose_review",
  "reference": "../../references/identity/volibear_approved.png",
  "canvas": [
    1312,
    1199
  ],
  "bones": {
    "root": {
      "parent": null,
      "rest_world": [
        675,
        850
      ],
      "local": [
        675.0,
        850.0
      ]
    },
    "pelvis": {
      "parent": "root",
      "rest_world": [
        675,
        850
      ],
      "local": [
        0,
        0
      ]
    },
    "spine": {
      "parent": "pelvis",
      "rest_world": [
        690,
        650
      ],
      "local": [
        15,
        -200
      ]
    },
    "chest": {
      "parent": "spine",
      "rest_world": [
        690,
        430
      ],
      "local": [
        0,
        -220
      ]
    },
    "neck": {
      "parent": "chest",
      "rest_world": [
        820,
        350
      ],
      "local": [
        130,
        -80
      ]
    },
    "head": {
      "parent": "neck",
      "rest_world": [
        870,
        310
      ],
      "local": [
        50,
        -40
      ]
    },
    "back": {
      "parent": "chest",
      "rest_world": [
        610,
        230
      ],
      "local": [
        -80,
        -200
      ]
    },
    "shoulder_near": {
      "parent": "chest",
      "rest_world": [
        530,
        360
      ],
      "local": [
        -160,
        -70
      ]
    },
    "elbow_near": {
      "parent": "shoulder_near",
      "rest_world": [
        340,
        550
      ],
      "local": [
        -190,
        190
      ]
    },
    "wrist_near": {
      "parent": "elbow_near",
      "rest_world": [
        195,
        760
      ],
      "local": [
        -145,
        210
      ]
    },
    "hand_tip_near": {
      "parent": "wrist_near",
      "rest_world": [
        205,
        865
      ],
      "local": [
        10,
        105
      ]
    },
    "shoulder_far": {
      "parent": "chest",
      "rest_world": [
        1000,
        525
      ],
      "local": [
        310,
        95
      ]
    },
    "elbow_far": {
      "parent": "shoulder_far",
      "rest_world": [
        1095,
        680
      ],
      "local": [
        95,
        155
      ]
    },
    "wrist_far": {
      "parent": "elbow_far",
      "rest_world": [
        1145,
        750
      ],
      "local": [
        50,
        70
      ]
    },
    "hand_tip_far": {
      "parent": "wrist_far",
      "rest_world": [
        1245,
        865
      ],
      "local": [
        100,
        115
      ]
    },
    "hip_near": {
      "parent": "pelvis",
      "rest_world": [
        540,
        800
      ],
      "local": [
        -135,
        -50
      ]
    },
    "knee_near": {
      "parent": "hip_near",
      "rest_world": [
        365,
        975
      ],
      "local": [
        -175,
        175
      ]
    },
    "ankle_near": {
      "parent": "knee_near",
      "rest_world": [
        260,
        1100
      ],
      "local": [
        -105,
        125
      ]
    },
    "toe_near": {
      "parent": "ankle_near",
      "rest_world": [
        250,
        1160
      ],
      "local": [
        -10,
        60
      ]
    },
    "hip_far": {
      "parent": "pelvis",
      "rest_world": [
        795,
        800
      ],
      "local": [
        120,
        -50
      ]
    },
    "knee_far": {
      "parent": "hip_far",
      "rest_world": [
        915,
        940
      ],
      "local": [
        120,
        140
      ]
    },
    "ankle_far": {
      "parent": "knee_far",
      "rest_world": [
        930,
        1080
      ],
      "local": [
        15,
        140
      ]
    },
    "toe_far": {
      "parent": "ankle_far",
      "rest_world": [
        955,
        1145
      ],
      "local": [
        25,
        65
      ]
    },
    "braid_near_0": {
      "parent": "neck",
      "rest_world": [
        755,
        365
      ],
      "local": [
        -65,
        15
      ]
    },
    "braid_near_1": {
      "parent": "braid_near_0",
      "rest_world": [
        755,
        485
      ],
      "local": [
        0,
        120
      ]
    },
    "braid_near_2": {
      "parent": "braid_near_1",
      "rest_world": [
        755,
        610
      ],
      "local": [
        0,
        125
      ]
    },
    "braid_near_3": {
      "parent": "braid_near_2",
      "rest_world": [
        755,
        740
      ],
      "local": [
        0,
        130
      ]
    },
    "braid_far_0": {
      "parent": "neck",
      "rest_world": [
        983,
        450
      ],
      "local": [
        163,
        100
      ]
    },
    "braid_far_1": {
      "parent": "braid_far_0",
      "rest_world": [
        983,
        550
      ],
      "local": [
        0,
        100
      ]
    },
    "braid_far_2": {
      "parent": "braid_far_1",
      "rest_world": [
        983,
        650
      ],
      "local": [
        0,
        100
      ]
    },
    "braid_far_3": {
      "parent": "braid_far_2",
      "rest_world": [
        983,
        770
      ],
      "local": [
        0,
        120
      ]
    }
  },
  "parts": {
    "thigh_far": {
      "file": "parts/thigh_far.png",
      "origin": [
        681,
        700
      ],
      "size": [
        316,
        357
      ],
      "bone": "hip_far",
      "z": 0,
      "source_bounds": [
        681,
        700,
        997,
        1057
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "shin_far": {
      "file": "parts/shin_far.png",
      "origin": [
        787,
        845
      ],
      "size": [
        296,
        246
      ],
      "bone": "knee_far",
      "z": 1,
      "source_bounds": [
        787,
        845,
        1083,
        1091
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "foot_far": {
      "file": "parts/foot_far.png",
      "origin": [
        749,
        1010
      ],
      "size": [
        369,
        189
      ],
      "bone": "ankle_far",
      "z": 2,
      "source_bounds": [
        749,
        1010,
        1118,
        1199
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "thigh_near": {
      "file": "parts/thigh_near.png",
      "origin": [
        259,
        656
      ],
      "size": [
        438,
        415
      ],
      "bone": "hip_near",
      "z": 3,
      "source_bounds": [
        259,
        656,
        697,
        1071
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "shin_near": {
      "file": "parts/shin_near.png",
      "origin": [
        162,
        880
      ],
      "size": [
        299,
        231
      ],
      "bone": "knee_near",
      "z": 4,
      "source_bounds": [
        162,
        880,
        461,
        1111
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "foot_near": {
      "file": "parts/foot_near.png",
      "origin": [
        128,
        1030
      ],
      "size": [
        327,
        164
      ],
      "bone": "ankle_near",
      "z": 5,
      "source_bounds": [
        128,
        1030,
        455,
        1194
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "upper_arm_far": {
      "file": "parts/upper_arm_far.png",
      "origin": [
        49,
        72
      ],
      "size": [
        1171,
        851
      ],
      "bone": "shoulder_far",
      "z": 6,
      "source_bounds": [
        49,
        72,
        1220,
        923
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "forearm_far": {
      "file": "parts/forearm_far.png",
      "origin": [
        641,
        555
      ],
      "size": [
        573,
        448
      ],
      "bone": "elbow_far",
      "z": 7,
      "source_bounds": [
        641,
        555,
        1214,
        1003
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "hand_far": {
      "file": "parts/hand_far.png",
      "origin": [
        1015,
        692
      ],
      "size": [
        297,
        252
      ],
      "bone": "wrist_far",
      "z": 8,
      "source_bounds": [
        1015,
        692,
        1312,
        944
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "upper_arm_socket_near": {
      "file": "parts/upper_arm_socket_near.png",
      "origin": [
        396,
        269
      ],
      "size": [
        304,
        248
      ],
      "bone": "shoulder_near",
      "z": 9.5,
      "source_bounds": [
        396,
        269,
        700,
        517
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "upper_arm_near": {
      "file": "parts/upper_arm_near.png",
      "origin": [
        177,
        270
      ],
      "size": [
        522,
        526
      ],
      "bone": "shoulder_near",
      "z": 15,
      "source_bounds": [
        177,
        270,
        699,
        796
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "forearm_near": {
      "file": "parts/forearm_near.png",
      "origin": [
        78,
        431
      ],
      "size": [
        348,
        360
      ],
      "bone": "elbow_near",
      "z": 16,
      "source_bounds": [
        78,
        431,
        426,
        791
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "hand_near": {
      "file": "parts/hand_near.png",
      "origin": [
        75,
        730
      ],
      "size": [
        607,
        203
      ],
      "bone": "wrist_near",
      "z": 17,
      "source_bounds": [
        75,
        730,
        682,
        933
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "back_spikes": {
      "file": "parts/back_spikes.png",
      "origin": [
        289,
        2
      ],
      "size": [
        536,
        361
      ],
      "bone": "back",
      "z": 9,
      "source_bounds": [
        289,
        2,
        825,
        363
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": null
    },
    "torso": {
      "file": "parts/torso.png",
      "origin": [
        340,
        127
      ],
      "size": [
        717,
        829
      ],
      "bone": "chest",
      "z": 10,
      "source_bounds": [
        340,
        127,
        1057,
        956
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": "torso"
    },
    "head": {
      "file": "parts/head.png",
      "origin": [
        700,
        145
      ],
      "size": [
        440,
        370
      ],
      "bone": "head",
      "z": 11,
      "source_bounds": [
        700,
        145,
        1140,
        515
      ],
      "mesh": "head",
      "overlap": "rounded rear head with per-cel clean jaw silhouette",
      "cels": [
        "parts/head.png",
        "parts/head_half.png",
        "parts/head_open.png"
      ]
    },
    "braid_near": {
      "file": "parts/braid_near.png",
      "origin": [
        700,
        343
      ],
      "size": [
        120,
        501
      ],
      "bone": "braid_near_0",
      "z": 13,
      "source_bounds": [
        700,
        343,
        820,
        844
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": "braid_near"
    },
    "braid_far": {
      "file": "parts/braid_far.png",
      "origin": [
        940,
        430
      ],
      "size": [
        90,
        431
      ],
      "bone": "braid_far_0",
      "z": 10,
      "source_bounds": [
        940,
        430,
        1030,
        861
      ],
      "overlap": "painted source surface retained beyond joint; rounded overlapping caps",
      "mesh": "braid_far"
    }
  },
  "principle": "Complete overlapping anatomical surfaces; visual reference similarity, not zero pixel difference",
  "production_approved": false
}
;
