{
  "broker": {
    "default": null
  },
  "connection": {
    "default": {
      "ethernet": {
        "data_buffer": 10100,
        "ip": "",
        "port": 5051
      }
    }
  },
  "connector": {
    "default": {
      "downloadPath": "system://HaasMachineTool",
      "ip": "127.0.0.1",
      "port": 50000
    }
  },
  "controller": {
    "default": {
      "head_info_part_id": "head",
      "max_block_processing_speed": 0,
      "max_normal_speed": 22900,
      "non_tcp_rapid_interpolation_mode": "Synchronized",
      "parts": {
        "X": {
          "coordinate": 0,
          "max_normal_speed": 16500,
          "max_rapid_speed": 22900,
          "preference": "negative",
          "reset": "never",
          "reversed": false,
          "tcp": false,
          "zero_position_offset": 0
        },
        "Y": {
          "coordinate": 1,
          "max_normal_speed": 16500,
          "max_rapid_speed": 22900,
          "preference": "negative",
          "reset": "never",
          "reversed": false,
          "tcp": false,
          "zero_position_offset": 0
        },
        "Z": {
          "coordinate": 2,
          "max_normal_speed": 16500,
          "max_rapid_speed": 22900,
          "preference": "negative",
          "reset": "never",
          "reversed": false,
          "tcp": false,
          "zero_position_offset": 0
        },
        "rotary_0": {
          "coordinate": 1,
          "max_normal_speed": 3000,
          "max_rapid_speed": 3000,
          "preference": "no preference",
          "reset": "never",
          "reversed": false,
          "tcp": true,
          "zero_position_offset": 0
        },
        "rotary_1": {
          "coordinate": 2,
          "max_normal_speed": 3000,
          "max_rapid_speed": 3000,
          "preference": "no preference",
          "reset": "never",
          "reversed": false,
          "tcp": true,
          "zero_position_offset": 0
        }
      },
      "table_part_id": "table",
      "tcp_rapid_interpolation_mode": "ToolTip"
    }
  },
  "fusion": {
    "default": {
      "image": "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",
      "imageAutoGenerated": true,
      "model_urn": "urn:adsk.wipprod:fs.file:vf.07xIxOIIRTes4CWHH0lRDw?version=1",
      "model_urn_kind": "model"
    }
  },
  "general": {
    "capabilities": [
      "milling"
    ],
    "description": "Silta UMC750 - single-tool indexed five-axis demo",
    "minimumRevision": 45805,
    "model": "UMC-750 Reboot",
    "vendor": "HAAS"
  },
  "interactions": {
    "default": {
      "pairs": [
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "rotary_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "rotary_1",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "rotary_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "rotary_1",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "rotary_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "rotary_1",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "machine_part"
            },
            {
              "id": "rotary_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "tool"
            },
            {
              "id": "rotary_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "machine_part"
            },
            {
              "id": "rotary_1",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "tool"
            },
            {
              "id": "rotary_1",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "tool"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "tool"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "tool"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "rotary_0",
              "type": "machine_part"
            },
            {
              "id": "rotary_1",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "rotary_0",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "rotary_0",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "rotary_0",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "rotary_1",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "rotary_1",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "stock"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "rotary_1",
              "type": "machine_part"
            },
            {
              "id": "table",
              "type": "fixture"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "Y",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "Z",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "head",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "head",
              "type": "tool"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "Z",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "head",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "head",
              "type": "tool"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "head",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "head",
              "type": "tool"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "X",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Y",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "Z",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "rotary_0",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": null,
          "solids": [
            {
              "id": "rotary_1",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "table",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "table",
              "type": "stock"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "table",
              "type": "fixture"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "machine_part"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        },
        {
          "setting": [
            "check_collisions"
          ],
          "solids": [
            {
              "id": "head",
              "type": "tool"
            },
            {
              "id": "static_0",
              "type": "machine_part"
            }
          ]
        }
      ]
    }
  },
  "kinematics": {
    "default": {
      "conventions": {
        "rotation": "right-handed"
      },
      "parts": [
        {
          "control": "driven",
          "direction": [
            1,
            0,
            0
          ],
          "home": -736.6,
          "id": "X",
          "max": 0,
          "min": -762,
          "name": "X",
          "parts": [
            {
              "control": "driven",
              "direction": [
                0,
                1,
                0
              ],
              "home": -203.2,
              "id": "Y",
              "max": 0,
              "min": -508,
              "name": "Y",
              "parts": [
                {
                  "control": "driven",
                  "direction": [
                    0,
                    0,
                    1
                  ],
                  "home": 63.5,
                  "id": "Z",
                  "max": 63.5,
                  "min": -508,
                  "name": "Z",
                  "parts": [
                    {
                      "attach_frame": {
                        "point": [
                          330.0000004124761,
                          254.00000030833297,
                          618.8900004788441
                        ],
                        "x_direction": [
                          1,
                          0,
                          0
                        ],
                        "z_direction": [
                          0,
                          0,
                          1
                        ]
                      },
                      "display_name": "head",
                      "id": "head",
                      "spindle": {
                        "max_speed": 8100,
                        "min_speed": 0
                      },
                      "tool_station": {
                        "coolants": [
                          "air",
                          "air_through_tool",
                          "flood",
                          "flood_through_tool",
                          "through_tool"
                        ],
                        "max_tool_diameter": 0,
                        "max_tool_length": 0
                      },
                      "type": "head"
                    }
                  ],
                  "type": "linear"
                }
              ],
              "type": "linear"
            }
          ],
          "type": "linear"
        },
        {
          "axis_of_rotation": {
            "direction": [
              0,
              -1,
              0
            ],
            "point": [
              -3.34684142017748e-07,
              -453.5294968,
              50.800000088
            ]
          },
          "control": "driven",
          "id": "rotary_0",
          "max": 110,
          "min": -35,
          "name": "B",
          "offset": [
            0,
            0,
            0
          ],
          "parts": [
            {
              "axis_of_rotation": {
                "direction": [
                  0,
                  0,
                  -1
                ],
                "point": [
                  7.31115223870188e-14,
                  2.2204460492503103e-13,
                  -1.35963107344689e-29
                ]
              },
              "control": "driven",
              "id": "rotary_1",
              "name": "C",
              "offset": [
                0,
                0,
                0
              ],
              "parts": [
                {
                  "attach_frame": {
                    "point": [
                      7.31115223870188e-14,
                      2.2204460492503103e-13,
                      -1.35963107344689e-29
                    ],
                    "x_direction": [
                      1,
                      0,
                      0
                    ],
                    "z_direction": [
                      0,
                      0,
                      1
                    ]
                  },
                  "display_name": "table",
                  "id": "table",
                  "type": "table"
                }
              ],
              "type": "rotary"
            }
          ],
          "type": "rotary"
        },
        {
          "display_name": "static_0",
          "id": "static_0",
          "type": "static"
        }
      ],
      "units": {
        "angle": "degrees",
        "length": "mm"
      }
    }
  },
  "machining": {
    "default": {
      "feedrate_ratio": 1,
      "tool_change_time": 15
    }
  },
  "multiaxis": {
    "default": {
      "feedrate": {
        "BPW_ratio": 1,
        "max_feedrate": 9999.99,
        "method": "FPM",
        "output_tolerance": 0.5,
        "type": "combination"
      },
      "retract_and_reconfigure": {
        "enabled": false,
        "retract_preference": "RetractAtApex",
        "rewind_preference": "RewindAtLinear",
        "rewind_strategy": "MinimizeRewinds",
        "safe_plunge_feedrate": 250,
        "safe_retract_distance": 25,
        "safe_retract_feedrate": 500,
        "stock_expansion": [
          2.5,
          2.5,
          2.5
        ]
      },
      "singularity": {
        "adjust": true,
        "angle": 0.17453292519943295,
        "cone": 0.05235987755982989,
        "linearization_tolerance": 0.04,
        "method": "rotary",
        "tolerance": 0.04
      },
      "use_tilted_workplane": true,
      "virtual_tool_tip": false
    }
  },
  "post": {
    "default": {
      "path": "system://haas next generation.cps"
    }
  },
  "tooling": {
    "default": {
      "has_tool_changer": true,
      "number_of_tools": 30,
      "supports_tool_preload": true
    }
  }
}
